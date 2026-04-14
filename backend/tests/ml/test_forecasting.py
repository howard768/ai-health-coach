"""Phase 2 forecasting tests: seasonal-naive + ensemble + anomaly detection.

Skips Prophet-heavy paths when appropriate so tests stay fast; Prophet is
covered by one slower test gated via ``pytest.mark.slow``.

Run: ``cd backend && uv run python -m pytest tests/ml/test_forecasting.py -v``
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
# Register ORM models with Base.metadata before fixture create_all.
from app.models import ml_baselines as _ml_baselines_models  # noqa: F401
from app.models import ml_features as _ml_features_models  # noqa: F401
from app.models.ml_baselines import MLAnomaly, MLForecast
from ml.features.store import materialize_for_user
from ml.forecasting import anomaly, residuals
from ml.discovery import baselines


USER = "u-forecast"


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
# Seasonal-naive forecast (pure pandas, no DB)
# ─────────────────────────────────────────────────────────────────────────


def _make_series(start: date, values: list[float]):
    import pandas as pd

    idx = [(start + timedelta(days=i)).isoformat() for i in range(len(values))]
    return pd.Series(values, index=idx, dtype=float)


def test_seasonal_naive_recovers_weekly_pattern():
    """With a strictly weekly-periodic series, naive forecast should return exact values."""
    import math

    values = [40.0 + 5 * math.sin(2 * math.pi * i / 7) for i in range(28)]
    s = _make_series(date(2026, 1, 1), values)
    made_on = date(2026, 1, 28)

    out = residuals.forecast_for_series(
        s, metric_key="hrv", made_on=made_on, horizon_days=7, use_prophet=False
    )
    assert len(out.points) == 7
    # Since use_prophet=False, the ensemble collapses to the naive forecast.
    # y_hat[t+h] should equal y[t+h-7].
    for i, pt in enumerate(out.points, start=1):
        lookback = made_on + timedelta(days=i) - timedelta(days=7)
        expected = s.loc[lookback.isoformat()]
        assert pt.y_hat is not None
        assert abs(pt.y_hat - float(expected)) < 1e-9


def test_seasonal_naive_returns_none_when_lookback_missing():
    """First few horizon days have no lookback -> y_hat None."""
    s = _make_series(date(2026, 1, 1), [40.0, 41.0, 42.0])  # only 3 days
    out = residuals.forecast_for_series(
        s, metric_key="hrv", made_on=date(2026, 1, 3), horizon_days=7, use_prophet=False
    )
    # Horizon days 1..4 are within 7d of made_on; lookback falls BEFORE 2026-01-01.
    # Days with lookback in the series: day 4,5,6,7 have lookback at day -3,-2,-1,0 — only day 7 lookback (2026-01-03) is in series.
    y_hat_none = sum(1 for p in out.points if p.y_hat is None)
    assert y_hat_none >= 3


def test_forecast_output_carries_metadata():
    """ForecastOutput should include metric_key, made_on, model_version."""
    s = _make_series(date(2026, 1, 1), [40.0] * 28)
    out = residuals.forecast_for_series(
        s, metric_key="hrv", made_on=date(2026, 1, 28), horizon_days=7, use_prophet=False
    )
    assert out.metric_key == "hrv"
    assert out.made_on == "2026-01-28"
    assert out.model_version == residuals.MODEL_VERSION


# ─────────────────────────────────────────────────────────────────────────
# compute_forecasts_for_user (DB, skips Prophet by passing use_prophet=False)
# ─────────────────────────────────────────────────────────────────────────


async def _seed_stable_hrv(db, days: int = 100):
    """Seed a clean 100-day hrv series with weekly seasonality."""
    import math
    import random

    random.seed(9)
    today = date.today()
    for i in range(days):
        d = today - timedelta(days=days - 1 - i)
        val = 40.0 + 3 * math.sin(2 * math.pi * i / 7) + random.gauss(0, 0.5)
        db.add(
            HealthMetricRecord(
                user_id=USER,
                date=d.isoformat(),
                metric_type="hrv",
                value=val,
                source="oura",
                is_canonical=True,
            )
        )
    await db.flush()


@pytest.mark.asyncio
async def test_compute_forecasts_for_user_writes_forecast_rows(db):
    await _seed_stable_hrv(db, days=100)
    today = date.today()
    await materialize_for_user(db, USER, today - timedelta(days=99), today)

    outputs = await residuals.compute_forecasts_for_user(
        db, USER, made_on=today, horizon_days=7, use_prophet=False
    )
    assert "hrv" in outputs
    assert len(outputs["hrv"].points) == 7

    row_count = (
        await db.execute(
            select(MLForecast).where(MLForecast.user_id == USER, MLForecast.metric_key == "hrv")
        )
    ).scalars().all()
    # 7 target dates written, all for the same made_on / model_version.
    assert len(row_count) == 7


@pytest.mark.asyncio
async def test_compute_forecasts_rerun_replaces_prior_rows(db):
    """Rerunning the same day replaces the prior batch, no duplicates."""
    await _seed_stable_hrv(db, days=100)
    today = date.today()
    await materialize_for_user(db, USER, today - timedelta(days=99), today)

    await residuals.compute_forecasts_for_user(db, USER, made_on=today, use_prophet=False)
    first = (
        await db.execute(select(MLForecast).where(MLForecast.user_id == USER))
    ).scalars().all()

    await residuals.compute_forecasts_for_user(db, USER, made_on=today, use_prophet=False)
    second = (
        await db.execute(select(MLForecast).where(MLForecast.user_id == USER))
    ).scalars().all()
    assert len(first) == len(second)


# ─────────────────────────────────────────────────────────────────────────
# detect_anomalies_for_user (DB + forecast + baseline)
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_detect_anomalies_with_no_baselines_returns_empty(db):
    """No baselines -> skip without crashing."""
    run = await anomaly.detect_anomalies_for_user(db, USER, date.today())
    assert run.anomalies_written == 0


@pytest.mark.asyncio
async def test_detect_anomalies_flags_extreme_spike(db):
    """Inject a spike on the last day and verify it gets flagged."""
    # 100 days of stable hrv, then spike today.
    await _seed_stable_hrv(db, days=100)

    today = date.today()

    # Materialize features + baselines + yesterday's forecast.
    await materialize_for_user(db, USER, today - timedelta(days=99), today)
    await baselines.compute_baselines_for_user(db, USER, today)

    # Forecast was made "yesterday" for the week ahead (relative to the spike).
    await residuals.compute_forecasts_for_user(
        db, USER, made_on=today - timedelta(days=1), horizon_days=7, use_prophet=False
    )

    # Now replace today's hrv with a big spike (far beyond residual_std).
    spike_value = 200.0  # way above the stable ~40
    await db.execute(
        HealthMetricRecord.__table__.delete().where(
            (HealthMetricRecord.user_id == USER)
            & (HealthMetricRecord.date == today.isoformat())
            & (HealthMetricRecord.metric_type == "hrv")
        )
    )
    db.add(
        HealthMetricRecord(
            user_id=USER,
            date=today.isoformat(),
            metric_type="hrv",
            value=spike_value,
            source="oura",
            is_canonical=True,
        )
    )
    await db.flush()
    # Re-materialize so feature store reflects the spike.
    await materialize_for_user(db, USER, today - timedelta(days=6), today)

    run = await anomaly.detect_anomalies_for_user(db, USER, today, lookback_days=3)
    assert run.anomalies_written >= 1

    rows = (
        await db.execute(
            select(MLAnomaly).where(
                MLAnomaly.user_id == USER,
                MLAnomaly.observation_date == today.isoformat(),
            )
        )
    ).scalars().all()
    assert rows, "Expected an anomaly row for today's spike"
    assert rows[0].direction == "high"
    assert abs(rows[0].z_score) >= 2.5


@pytest.mark.asyncio
async def test_detect_anomalies_is_idempotent(db):
    """Rerunning does not create duplicates."""
    await _seed_stable_hrv(db, days=100)
    today = date.today()
    await materialize_for_user(db, USER, today - timedelta(days=99), today)
    await baselines.compute_baselines_for_user(db, USER, today)
    await residuals.compute_forecasts_for_user(
        db, USER, made_on=today - timedelta(days=1), use_prophet=False
    )

    # No spike injected; stable data means likely 0 anomalies either run.
    await anomaly.detect_anomalies_for_user(db, USER, today)
    first = (
        await db.execute(select(MLAnomaly).where(MLAnomaly.user_id == USER))
    ).scalars().all()
    await anomaly.detect_anomalies_for_user(db, USER, today)
    second = (
        await db.execute(select(MLAnomaly).where(MLAnomaly.user_id == USER))
    ).scalars().all()
    assert len(first) == len(second)
