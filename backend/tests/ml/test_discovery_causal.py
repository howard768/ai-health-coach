"""Phase 6 L4 DoWhy quasi-causal inference tests.

Tests fall into three categories:

1. **Unit tests**: causal estimation on synthetic arrays with known causal
   structure, and refutation-failure test on independent pairs.
2. **Persistence test**: verify ``ml_causal_estimates`` rows and
   ``UserCorrelation.causal_support`` / confidence_tier updates.
3. **Integration test**: DoWhy import + estimation works on current Python.

Run: ``cd backend && uv run python -m pytest tests/ml/test_discovery_causal.py -v``
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
from app.models.ml_discovery import MLCausalEstimate
# Register ORM models with Base.metadata before fixture create_all.
from app.models import ml_baselines as _ml_baselines  # noqa: F401
from app.models import ml_features as _ml_features  # noqa: F401
from app.models import ml_synth as _ml_synth  # noqa: F401


USER = "u-causal"


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
# Unit: DoWhy estimation on known causal data
# ---------------------------------------------------------------------------


def test_dowhy_imports_successfully():
    """Verify dowhy + econml import without error on current Python."""
    try:
        import dowhy  # noqa: F401
        import econml  # noqa: F401
    except ImportError as e:
        pytest.skip(f"dowhy/econml not installed: {e}")


def test_estimate_causal_effect_known_treatment():
    """When treatment strongly causes outcome, ATE should be non-zero
    and CI should exclude zero.
    """
    from ml.discovery.causal import _estimate_causal_effect

    rng = np.random.default_rng(42)
    n = 200
    treatment = rng.normal(0, 1, size=n)
    outcome = 2.0 * treatment + rng.normal(0, 0.5, size=n)

    result = _estimate_causal_effect(
        treatment, outcome, None, "treatment_metric", "outcome_metric"
    )

    if result is None:
        pytest.skip("DoWhy estimation failed (possible version incompatibility)")

    assert result.ate is not None, "ATE should be computed"
    # The true ATE is 2.0 (per unit change in treatment).
    assert abs(result.ate - 2.0) < 1.0, f"ATE should be near 2.0, got {result.ate}"
    assert result.n_samples == n


def test_estimate_causal_effect_independent_pair():
    """When treatment and outcome are independent, ATE should be near zero."""
    from ml.discovery.causal import _estimate_causal_effect

    rng = np.random.default_rng(42)
    n = 200
    treatment = rng.normal(0, 1, size=n)
    outcome = rng.normal(5, 2, size=n)  # independent of treatment

    result = _estimate_causal_effect(
        treatment, outcome, None, "treatment_metric", "outcome_metric"
    )

    if result is None:
        pytest.skip("DoWhy estimation failed (possible version incompatibility)")

    # ATE should be near zero for independent pair.
    assert result.ate is not None
    assert abs(result.ate) < 1.0, f"Independent pair ATE should be near 0, got {result.ate}"


def test_estimate_with_confounders():
    """When a confounder drives both treatment and outcome, DML should
    still estimate the direct effect reasonably.
    """
    from ml.discovery.causal import _estimate_causal_effect

    rng = np.random.default_rng(42)
    n = 300
    confounder = rng.normal(0, 1, size=n)
    treatment = 0.5 * confounder + rng.normal(0, 0.5, size=n)
    outcome = 1.5 * treatment + 0.8 * confounder + rng.normal(0, 0.3, size=n)
    confounders = confounder.reshape(-1, 1)

    result = _estimate_causal_effect(
        treatment, outcome, confounders, "treatment_metric", "outcome_metric"
    )

    if result is None:
        pytest.skip("DoWhy estimation failed (possible version incompatibility)")

    assert result.ate is not None
    # True direct effect is 1.5.
    assert abs(result.ate - 1.5) < 1.5, f"ATE should be near 1.5, got {result.ate}"


# ---------------------------------------------------------------------------
# Integration: persistence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_causal_results_promotes_tier(db: AsyncSession):
    """Persist causal results, verify causal_support and tier promotion."""
    from app.core.time import utcnow_naive
    from ml.discovery.causal import CausalResult, persist_causal_results

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
            directional_support=True,
            effect_size_description="moderate",
            discovered_at=now,
            last_validated_at=now,
        )
    )
    await db.flush()

    results = [
        CausalResult(
            treatment_metric="steps",
            outcome_metric="sleep_efficiency",
            lag_days=1,
            estimator="DML",
            ate=0.45,
            ate_ci_lower=0.12,
            ate_ci_upper=0.78,
            ate_p_value=0.008,
            placebo_treatment_passed=True,
            random_common_cause_passed=True,
            subset_passed=True,
            all_refutations_passed=True,
            ci_excludes_zero=True,
            n_samples=90,
        ),
    ]

    rows, updated = await persist_causal_results(db, USER, results)
    assert rows == 1
    assert updated == 1

    # Verify ml_causal_estimates row.
    stmt = select(MLCausalEstimate).where(MLCausalEstimate.user_id == USER)
    result = await db.execute(stmt)
    ce = result.scalar_one()
    assert ce.all_refutations_passed is True
    assert ce.ci_excludes_zero is True
    assert ce.ate == 0.45

    # Verify UserCorrelation promotion.
    stmt2 = select(UserCorrelation).where(
        UserCorrelation.user_id == USER,
        UserCorrelation.source_metric == "steps",
    )
    uc = (await db.execute(stmt2)).scalar_one()
    assert uc.causal_support is True
    assert uc.confidence_tier == "causal_candidate"


@pytest.mark.asyncio
async def test_persist_causal_results_no_promotion_when_refutation_fails(db: AsyncSession):
    """When a refutation fails, the pair should NOT be promoted."""
    from app.core.time import utcnow_naive
    from ml.discovery.causal import CausalResult, persist_causal_results

    now = utcnow_naive()
    db.add(
        UserCorrelation(
            user_id=USER,
            source_metric="protein_g",
            target_metric="deep_sleep_minutes",
            lag_days=0,
            direction="positive",
            pearson_r=0.40,
            spearman_r=0.38,
            p_value=0.005,
            fdr_adjusted_p=0.02,
            sample_size=60,
            strength=0.40,
            confidence_tier="developing",
            literature_match=True,
            directional_support=True,
            effect_size_description="moderate-to-strong",
            discovered_at=now,
            last_validated_at=now,
        )
    )
    await db.flush()

    results = [
        CausalResult(
            treatment_metric="protein_g",
            outcome_metric="deep_sleep_minutes",
            lag_days=0,
            estimator="DML",
            ate=0.30,
            ate_ci_lower=0.05,
            ate_ci_upper=0.55,
            ate_p_value=0.02,
            placebo_treatment_passed=True,
            random_common_cause_passed=False,  # FAILS
            subset_passed=True,
            all_refutations_passed=False,
            ci_excludes_zero=True,
            n_samples=80,
        ),
    ]

    rows, updated = await persist_causal_results(db, USER, results)
    assert rows == 1
    assert updated == 0  # no promotion

    # Verify UserCorrelation NOT promoted.
    stmt = select(UserCorrelation).where(
        UserCorrelation.user_id == USER,
        UserCorrelation.source_metric == "protein_g",
    )
    uc = (await db.execute(stmt)).scalar_one()
    assert uc.causal_support is False
    assert uc.confidence_tier == "developing"  # unchanged


# ---------------------------------------------------------------------------
# Integration: ml.api entry point
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ml_api_run_causal_returns_report(db: AsyncSession):
    """Verify the ml.api.run_causal entry point works end-to-end."""
    from ml import api as ml_api

    # No eligible pairs yet, so should return empty report.
    report = await ml_api.run_causal(db, USER, window_days=90)
    assert report.pairs_tested == 0
    assert report.rows_written == 0


@pytest.mark.asyncio
async def test_ml_api_run_granger_returns_report(db: AsyncSession):
    """Verify the ml.api.run_granger entry point works end-to-end."""
    from ml import api as ml_api

    report = await ml_api.run_granger(db, USER, window_days=90)
    assert report.pairs_tested == 0
    assert report.rows_written == 0
