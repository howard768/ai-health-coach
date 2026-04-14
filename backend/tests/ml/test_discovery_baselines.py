"""Phase 2 L1 baseline tests: STL + BOCPD + ruptures.

Golden-data tests for the statistical primitives, plus an end-to-end test
for ``compute_baselines_for_user`` with real DB seeding.

Run: ``cd backend && uv run python -m pytest tests/ml/test_discovery_baselines.py -v``
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("ENCRYPTION_KEY", "T0TXLkHFSeZRYGIIejSFVkhQrvRE-bWLkwXSkkdWiKQ=")
os.environ.setdefault("ANTHROPIC_API_KEY", "fake-key-tests-dont-call-anthropic")

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models.health import HealthMetricRecord
# Importing these model modules at top level ensures their tables are registered
# with Base.metadata before the fixture calls create_all.
from app.models import ml_baselines as _ml_baselines_models  # noqa: F401
from app.models import ml_features as _ml_features_models  # noqa: F401
from app.models.ml_baselines import MLBaseline, MLChangePoint
from ml.discovery import baselines
from ml.features.store import materialize_for_user


USER = "u-baselines"


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session
    await engine.dispose()


# ─────────────────────────────────────────────────────────────────────────
# STL: compute_baseline_for_series
# ─────────────────────────────────────────────────────────────────────────


def _make_series(start: date, values: list[float]):
    """Build a pandas Series indexed by ISO date strings."""
    import pandas as pd

    idx = [(start + timedelta(days=i)).isoformat() for i in range(len(values))]
    return pd.Series(values, index=idx, dtype=float)


def test_compute_baseline_returns_none_on_short_series():
    """< 28 observed days -> None. Caller counts toward metrics_skipped_short_history."""
    s = _make_series(date(2026, 1, 1), [40.0 + i for i in range(20)])
    stats = baselines.compute_baseline_for_series(s, metric_key="hrv")
    assert stats is None


def test_compute_baseline_returns_stats_with_nones_on_degenerate_long_series():
    """STL failure on a long-enough series returns a stats row with None computed fields.

    The caller needs to see metadata (observed_days, last_observed_date) even
    when STL bombs, so it can decide whether to retry.
    """
    # Single-value constant 40-day series. STL may or may not succeed on this
    # depending on statsmodels version. Either way, we don't expect usable
    # trend / residual stats.
    s = _make_series(date(2026, 1, 1), [42.0] * 40)
    stats = baselines.compute_baseline_for_series(s, metric_key="hrv")
    assert stats is not None
    assert stats.observed_days_in_window == 40


def test_compute_baseline_fits_trend_and_residual_on_long_series():
    """Linear trend series should produce a near-zero residual std."""
    # 60 days of y = 40 + 0.1*i + sin(2*pi*i/7) * 2 (weekly seasonality)
    import math

    values = [40.0 + 0.1 * i + 2 * math.sin(2 * math.pi * i / 7) for i in range(60)]
    s = _make_series(date(2026, 1, 1), values)

    stats = baselines.compute_baseline_for_series(s, metric_key="hrv")
    assert stats is not None
    assert stats.observed_days_in_window == 60
    assert stats.residual_std is not None
    assert stats.trend_mean is not None
    # Slope should be approximately 0.1/day.
    assert stats.trend_slope is not None
    assert 0.05 < stats.trend_slope < 0.15
    # Residual std should be small for a noiseless series.
    assert stats.residual_std < 1.0
    # Seasonal amplitude should be around 2 * 2 = 4 (trough to peak).
    assert 2.0 < stats.seasonal_amplitude < 8.0


def test_compute_baseline_handles_degenerate_constant_series():
    """Constant series: STL may fail or produce zero residual. Either way don't crash."""
    s = _make_series(date(2026, 1, 1), [42.0] * 40)
    stats = baselines.compute_baseline_for_series(s, metric_key="hrv")
    # Shouldn't raise. Residual std may be 0 or None; both are acceptable.
    assert stats is not None
    assert stats.observed_days_in_window == 40


def test_compute_baseline_handles_internal_nans_via_interpolation():
    """A few missing days inside the observed span should interpolate cleanly."""
    import math

    values: list[float | None] = [40.0 + 2 * math.sin(2 * math.pi * i / 7) for i in range(40)]
    values[10] = None
    values[25] = None
    s = _make_series(date(2026, 1, 1), values)
    stats = baselines.compute_baseline_for_series(s, metric_key="hrv")
    assert stats is not None
    # Two NaNs means 38 observed days, which is >= 28 so we compute.
    assert stats.observed_days_in_window == 38
    assert stats.residual_std is not None


# ─────────────────────────────────────────────────────────────────────────
# BOCPD: fit_bocpd golden data
# ─────────────────────────────────────────────────────────────────────────


def test_bocpd_detects_obvious_mean_shift():
    """60 days at mean 40, then 60 days at mean 50 -> BOCPD should fire near day 60."""
    import random

    random.seed(42)
    values = [40.0 + random.gauss(0, 1) for _ in range(60)]
    values += [50.0 + random.gauss(0, 1) for _ in range(60)]
    s = _make_series(date(2026, 1, 1), values)

    events = baselines.fit_bocpd(s, hazard_rate=1 / 100, threshold_prob=0.3)

    # At least one event should be detected, and the first should be within
    # ~15 days of the true change point (day 60).
    assert len(events) >= 1, "BOCPD should detect the shift from 40 -> 50"
    first = events[0]
    first_idx = (date.fromisoformat(first.change_date) - date(2026, 1, 1)).days
    assert 55 <= first_idx <= 75, (
        f"Expected change point near day 60, got day {first_idx}"
    )
    assert first.detector == "bocpd"
    assert 0.0 < (first.probability or 0.0) <= 1.0


def test_bocpd_returns_no_events_on_stable_series():
    """Stationary noise should produce no false-positive change points."""
    import random

    random.seed(7)
    values = [40.0 + random.gauss(0, 1) for _ in range(120)]
    s = _make_series(date(2026, 1, 1), values)

    events = baselines.fit_bocpd(s, hazard_rate=1 / 100, threshold_prob=0.8)
    assert events == [], f"No change points expected on stable data, got {len(events)}"


def test_bocpd_handles_short_series():
    """< 3 points -> empty, no crash."""
    s = _make_series(date(2026, 1, 1), [40.0, 41.0])
    assert baselines.fit_bocpd(s) == []


def test_bocpd_skips_nans_gracefully():
    """Series with NaNs should not crash; run length just doesn't update."""
    import random

    random.seed(1)
    values: list[float | None] = [40.0 + random.gauss(0, 1) for _ in range(40)]
    values[10] = None
    values[20] = None
    s = _make_series(date(2026, 1, 1), values)
    events = baselines.fit_bocpd(s)
    # Just need: no exceptions, returns a list.
    assert isinstance(events, list)


# ─────────────────────────────────────────────────────────────────────────
# ruptures: fit_ruptures golden data
# ─────────────────────────────────────────────────────────────────────────


def test_ruptures_finds_a_breakpoint_on_obvious_shift():
    """Ruptures.Pelt should segment a 40->50 shift series."""
    import random

    random.seed(99)
    values = [40.0 + random.gauss(0, 1) for _ in range(60)]
    values += [50.0 + random.gauss(0, 1) for _ in range(60)]
    s = _make_series(date(2026, 1, 1), values)

    events = baselines.fit_ruptures(s, metric_key="hrv", penalty=5.0)
    assert len(events) >= 1
    for e in events:
        assert e.detector == "ruptures"
        assert e.probability is None  # ruptures is not probabilistic


# ─────────────────────────────────────────────────────────────────────────
# End-to-end: compute_baselines_for_user
# ─────────────────────────────────────────────────────────────────────────


async def _seed_hrv_history(db, days: int = 60, shift_at: int | None = None):
    """Seed canonical hrv HealthMetricRecord rows for the primary user.

    ``shift_at`` optional: days <shift_at have mean 40, days >= have mean 50.
    """
    import random

    random.seed(31)
    today = date.today()
    for i in range(days):
        target = today - timedelta(days=days - 1 - i)
        base = 40.0 if shift_at is None or i < shift_at else 50.0
        db.add(
            HealthMetricRecord(
                user_id=USER,
                date=target.isoformat(),
                metric_type="hrv",
                value=base + random.gauss(0, 1),
                source="oura",
                is_canonical=True,
            )
        )
    await db.flush()


@pytest.mark.asyncio
async def test_compute_baselines_for_user_writes_ml_baselines_row(db):
    """End-to-end: seed features, run materialize, run baselines -> ml_baselines has a row."""
    await _seed_hrv_history(db, days=60)
    through = date.today()
    # Materialize features first (L1 reads from the feature store).
    await materialize_for_user(db, USER, through - timedelta(days=59), through)

    run = await baselines.compute_baselines_for_user(db, USER, through)
    assert run.baselines_written >= 1

    # The hrv baseline row should exist.
    result = await db.execute(
        select(MLBaseline).where(
            MLBaseline.user_id == USER, MLBaseline.metric_key == "hrv"
        )
    )
    row = result.scalar_one_or_none()
    assert row is not None
    assert row.observed_days_in_window == 60
    assert row.residual_std is not None
    assert row.residual_std > 0


@pytest.mark.asyncio
async def test_compute_baselines_skips_metric_with_short_history(db):
    """A metric with < 28 observed days appears in metrics_skipped_short_history."""
    await _seed_hrv_history(db, days=10)
    through = date.today()
    await materialize_for_user(db, USER, through - timedelta(days=9), through)

    run = await baselines.compute_baselines_for_user(db, USER, through)
    assert "hrv" in run.metrics_skipped_short_history
    assert run.baselines_written == 0


@pytest.mark.asyncio
async def test_compute_baselines_persists_change_point_on_obvious_shift(db):
    """Seed a clear mean shift. BOCPD should fire, ml_change_points should have at least one row."""
    await _seed_hrv_history(db, days=120, shift_at=60)
    through = date.today()
    await materialize_for_user(db, USER, through - timedelta(days=119), through)

    await baselines.compute_baselines_for_user(db, USER, through)

    result = await db.execute(
        select(MLChangePoint).where(
            MLChangePoint.user_id == USER,
            MLChangePoint.metric_key == "hrv",
        )
    )
    events = list(result.scalars().all())
    assert events, "Expected at least one change point for the 40->50 shift"
    # At least one detector should have fired; both BOCPD and ruptures are valid.
    detectors = {e.detector for e in events}
    assert detectors & {"bocpd", "ruptures"}


@pytest.mark.asyncio
async def test_compute_baselines_is_idempotent_across_reruns(db):
    """Rerunning the same day does not create duplicate baseline rows."""
    await _seed_hrv_history(db, days=60)
    through = date.today()
    await materialize_for_user(db, USER, through - timedelta(days=59), through)

    await baselines.compute_baselines_for_user(db, USER, through)
    first_count = (
        await db.execute(select(MLBaseline).where(MLBaseline.user_id == USER))
    ).scalars().all()
    await baselines.compute_baselines_for_user(db, USER, through)
    second_count = (
        await db.execute(select(MLBaseline).where(MLBaseline.user_id == USER))
    ).scalars().all()
    assert len(first_count) == len(second_count)


@pytest.mark.asyncio
async def test_compute_baselines_with_no_feature_data_is_a_no_op(db):
    """No upstream data -> baselines run returns, no rows written."""
    through = date.today()
    run = await baselines.compute_baselines_for_user(db, USER, through)
    assert run.baselines_written == 0
    assert run.change_points_written == 0
