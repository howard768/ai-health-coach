"""Phase 6 L3 Granger causality tests.

Tests fall into three categories:

1. **Unit tests**: ADF stationarity, Granger F-test on synthetic arrays with
   known causal structure.
2. **Golden-data test**: end-to-end via ``ml.api.run_granger`` on a synth
   user from Phase 4.5's factory. The shared latent in the wearable generator
   guarantees Granger sees real joint dependence. This is the whole reason
   Phase 4.5 had to ship before Phase 6.
3. **Persistence test**: verify ``ml_directional_tests`` rows and
   ``UserCorrelation.directional_support`` updates.

Run: ``cd backend && uv run python -m pytest tests/ml/test_discovery_granger.py -v``
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("ENCRYPTION_KEY", "T0TXLkHFSeZRYGIIejSFVkhQrvRE-bWLkwXSkkdWiKQ=")
os.environ.setdefault("ANTHROPIC_API_KEY", "fake-key-tests-dont-call-anthropic")

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models.correlation import UserCorrelation
from app.models.ml_discovery import MLDirectionalTest
# Register ORM models with Base.metadata before fixture create_all.
from app.models import ml_baselines as _ml_baselines  # noqa: F401
from app.models import ml_features as _ml_features  # noqa: F401
from app.models import ml_synth as _ml_synth  # noqa: F401
from ml.discovery.granger import (
    _check_stationarity,
    _ensure_stationary,
    _run_granger_test,
    compute_granger_for_pair,
)


USER = "u-granger"


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


# ---------------------------------------------------------------------------
# Unit: stationarity
# ---------------------------------------------------------------------------


def test_stationary_white_noise_passes_adf():
    """White noise should be stationary."""
    rng = np.random.default_rng(42)
    series = rng.normal(0, 1, size=100)
    is_stat, p = _check_stationarity(series)
    assert is_stat, f"White noise should be stationary, got p={p:.4f}"


def test_random_walk_fails_adf():
    """A random walk should be non-stationary."""
    rng = np.random.default_rng(42)
    walk = np.cumsum(rng.normal(0, 1, size=100))
    is_stat, p = _check_stationarity(walk)
    assert not is_stat, f"Random walk should be non-stationary, got p={p:.4f}"


def test_ensure_stationary_first_differences_random_walk():
    """First-differencing a random walk should produce a stationary series."""
    rng = np.random.default_rng(42)
    walk_x = np.cumsum(rng.normal(0, 1, size=100))
    walk_y = np.cumsum(rng.normal(0, 1, size=100))
    x_s, y_s, is_stat, diff_order = _ensure_stationary(walk_x, walk_y)
    assert is_stat, "First-differenced random walk should be stationary"
    assert diff_order == 1
    assert len(x_s) == 99  # one less after differencing


# ---------------------------------------------------------------------------
# Unit: Granger test on known causal structure
# ---------------------------------------------------------------------------


def test_granger_detects_known_causal_lag():
    """When X[t-1] drives Y[t], Granger should find significance."""
    rng = np.random.default_rng(42)
    n = 200
    x = rng.normal(0, 1, size=n)
    y = np.zeros(n)
    for t in range(1, n):
        y[t] = 0.7 * x[t - 1] + 0.3 * rng.normal()

    f_stat, p_val, opt_lag = _run_granger_test(x, y, max_lag=5)
    assert f_stat is not None, "Granger should produce an F-statistic"
    assert p_val is not None and p_val < 0.05, f"Expected significant, got p={p_val}"
    assert opt_lag == 1, f"Expected optimal lag 1, got {opt_lag}"


def test_granger_rejects_independent_series():
    """Two independent series should not show Granger causality."""
    rng = np.random.default_rng(42)
    n = 200
    x = rng.normal(0, 1, size=n)
    y = rng.normal(0, 1, size=n)

    f_stat, p_val, _ = _run_granger_test(x, y, max_lag=5)
    # Independent series: p should be high (> 0.05).
    if p_val is not None:
        assert p_val > 0.05, f"Independent series should not be significant, p={p_val}"


# ---------------------------------------------------------------------------
# Unit: compute_granger_for_pair
# ---------------------------------------------------------------------------


def test_compute_granger_known_causal_pair():
    """End-to-end unit test on a known causal pair."""
    rng = np.random.default_rng(42)
    n = 150
    x = rng.normal(50, 10, size=n)
    y = np.zeros(n)
    for t in range(1, n):
        y[t] = 0.6 * x[t - 1] + 5 + rng.normal(0, 3)

    result = compute_granger_for_pair(x, y, "steps", "sleep_efficiency", lag_days=1)
    assert result is not None
    assert result.significant, "Known causal pair should be significant"
    assert result.p_value is not None and result.p_value < 0.05
    assert result.is_stationary


def test_compute_granger_insufficient_data_returns_none():
    """Fewer than MIN_OBSERVATIONS should return None."""
    x = np.array([1.0, 2.0, 3.0])
    y = np.array([4.0, 5.0, 6.0])
    result = compute_granger_for_pair(x, y, "a", "b", lag_days=0)
    assert result is None


def test_compute_granger_handles_nans():
    """NaN-laden series should still work if enough non-NaN values remain."""
    rng = np.random.default_rng(42)
    n = 100
    x = rng.normal(0, 1, size=n)
    y = np.zeros(n)
    for t in range(1, n):
        y[t] = 0.5 * x[t - 1] + rng.normal(0, 0.5)

    # Sprinkle NaNs.
    x[::10] = np.nan
    y[::15] = np.nan

    result = compute_granger_for_pair(x, y, "a", "b", lag_days=0)
    # Should still be able to test (n - nans > 30).
    assert result is not None


# ---------------------------------------------------------------------------
# Integration: persistence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_granger_results(db: AsyncSession):
    """Persist Granger results, verify directional_support update."""
    from app.core.time import utcnow_naive
    from ml.discovery.granger import GrangerResult, persist_granger_results

    # Seed a UserCorrelation row.
    now = utcnow_naive()
    db.add(
        UserCorrelation(
            user_id=USER,
            source_metric="steps",
            target_metric="sleep_efficiency",
            lag_days=1,
            direction="positive",
            pearson_r=0.35,
            spearman_r=0.32,
            p_value=0.01,
            fdr_adjusted_p=0.03,
            sample_size=60,
            strength=0.35,
            confidence_tier="developing",
            literature_match=False,
            effect_size_description="moderate",
            discovered_at=now,
            last_validated_at=now,
        )
    )
    await db.flush()

    results = [
        GrangerResult(
            source_metric="steps",
            target_metric="sleep_efficiency",
            lag_days=1,
            is_stationary=True,
            differencing_order=0,
            f_statistic=12.5,
            p_value=0.001,
            max_lag_tested=7,
            optimal_lag=1,
            significant=True,
        ),
    ]

    rows, updated = await persist_granger_results(db, USER, results)
    assert rows == 1
    assert updated == 1

    # Verify ml_directional_tests row.
    stmt = select(MLDirectionalTest).where(MLDirectionalTest.user_id == USER)
    result = await db.execute(stmt)
    dt = result.scalar_one()
    assert dt.significant is True
    assert dt.f_statistic == 12.5

    # Verify UserCorrelation update.
    stmt2 = select(UserCorrelation).where(
        UserCorrelation.user_id == USER,
        UserCorrelation.source_metric == "steps",
    )
    uc = (await db.execute(stmt2)).scalar_one()
    assert uc.directional_support is True


# ---------------------------------------------------------------------------
# Golden-data: synth user end-to-end
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_granger_on_synth_user_finds_directional_pair(db: AsyncSession):
    """The synth factory's shared latent should produce at least one
    Granger-significant pair among the developing+ associations.

    This is the critical integration test that validates the Phase 4.5 ->
    Phase 6 handshake: shared-latent wearable channels produce real
    Granger-detectable dependence, not spurious nulls from independent
    channels.
    """
    from ml import api as ml_api
    from ml.features.store import materialize_for_user
    from datetime import date, timedelta

    # 1. Generate 120-day synth user.
    manifest = await ml_api.generate_synth_cohort(
        db, n_users=1, days=120, seed=42
    )
    user_id = manifest.user_ids[0]
    await db.commit()

    # 2. Materialize features.
    today = date.today()
    start = today - timedelta(days=120)
    await materialize_for_user(db, user_id, start, today)
    await db.commit()

    # 3. Run L2 associations with a 60-day window to get developing+ pairs.
    assoc_report = await ml_api.run_associations(db, user_id, window_days=60)
    await db.commit()
    assert assoc_report.significant_results > 0, (
        "Synth user should have at least 1 significant L2 association"
    )

    # 4. Run L3 Granger.
    granger_report = await ml_api.run_granger(db, user_id, window_days=90)
    await db.commit()

    assert granger_report.pairs_tested > 0, (
        "Should test at least 1 developing+ pair"
    )

    # Verify at least one directional test row was written.
    stmt = select(MLDirectionalTest).where(MLDirectionalTest.user_id == user_id)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    assert len(rows) > 0, "Should write at least 1 ml_directional_tests row"

    # The shared latent guarantees at least one pair should show Granger
    # significance. This is the load-bearing invariant.
    significant_rows = [r for r in rows if r.significant]
    assert len(significant_rows) > 0, (
        "Synth user with shared latent should have at least 1 Granger-significant pair. "
        f"Tested {len(rows)} pairs, all failed. Check wearables.py shared-latent strength."
    )
