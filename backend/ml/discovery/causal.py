"""L4 quasi-causal inference: DoWhy + econml DML on L3-supported pairs.

Takes pairs from ``UserCorrelation`` that have ``directional_support=True``
or ``literature_match=True``, builds a DoWhy causal model with an assumed
DAG (treatment -> outcome, with observed confounders), estimates the ATE via
``econml.dml.DML``, and runs three refutation tests:

1. **Placebo treatment**: replace treatment with random noise.
2. **Random common cause**: add a random confounder.
3. **Subset data**: re-estimate on a random 80% subset.

A pair is promoted to ``causal_candidate`` confidence tier when the ATE 95%
CI excludes zero AND all three refuters pass.

All heavy imports (dowhy, econml, sklearn, pandas, numpy) are lazy inside
function bodies per the cold-boot contract.

Entry point is ``run_causal_for_user``, called from ``ml.api``.

See ``~/.claude/plans/golden-floating-creek.md`` line 173 (L4 row).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select

if TYPE_CHECKING:
    import numpy as np
    import pandas as pd
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

MODEL_VERSION = "causal-1.0.0"

# Configuration.
MIN_OBSERVATIONS = 40
REFUTATION_PLACEBO_NUM_SIMULATIONS = 100
REFUTATION_SUBSET_FRACTION = 0.8


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class CausalResult:
    """One DoWhy estimation outcome for a (treatment, outcome) pair."""

    treatment_metric: str
    outcome_metric: str
    lag_days: int
    estimator: str
    ate: float | None
    ate_ci_lower: float | None
    ate_ci_upper: float | None
    ate_p_value: float | None
    placebo_treatment_passed: bool
    random_common_cause_passed: bool
    subset_passed: bool
    all_refutations_passed: bool
    ci_excludes_zero: bool
    n_samples: int


@dataclass
class CausalReport:
    """Summary of a full causal estimation run for one user."""

    user_id: str
    pairs_tested: int = 0
    pairs_passed: int = 0
    pairs_skipped_insufficient_data: int = 0
    pairs_estimation_failed: int = 0
    rows_written: int = 0
    correlations_updated: int = 0
    timings_ms: dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Core estimation
# ---------------------------------------------------------------------------


def _build_causal_df(
    treatment: "np.ndarray",
    outcome: "np.ndarray",
    confounders: "np.ndarray | None",
) -> "pd.DataFrame":
    """Build a DataFrame with treatment, outcome, and confounder columns."""
    import pandas as pd

    data = {"treatment": treatment, "outcome": outcome}
    if confounders is not None and confounders.shape[1] > 0:
        for i in range(confounders.shape[1]):
            data[f"W{i}"] = confounders[:, i]
    return pd.DataFrame(data)


def _estimate_causal_effect(
    treatment: "np.ndarray",
    outcome: "np.ndarray",
    confounders: "np.ndarray | None",
    treatment_name: str,
    outcome_name: str,
) -> CausalResult | None:
    """Run econml LinearDML estimation + 3 refutation tests for one pair.

    Uses econml.dml.LinearDML directly (rather than DoWhy's string-based
    API, which has deprecation issues on econml >= 0.16 and requires
    pygraphviz). Refutation tests are implemented as permutation and
    subset re-estimation checks.

    Returns None if estimation raises an unrecoverable error.
    """
    import numpy as np

    try:
        from econml.dml import LinearDML
        from sklearn.ensemble import GradientBoostingRegressor
    except ImportError:
        logger.warning("econml not installed; skipping L4 causal estimation")
        return None

    n = len(treatment)
    T = treatment.reshape(-1, 1)
    Y = outcome

    try:
        dml = LinearDML(
            model_y=GradientBoostingRegressor(n_estimators=50, max_depth=3),
            model_t=GradientBoostingRegressor(n_estimators=50, max_depth=3),
            discrete_treatment=False,
        )
        dml.fit(Y, T, W=confounders)

        ate = float(dml.ate())
        ci = dml.ate_interval(alpha=0.05)
        ate_ci_lower = float(ci[0])
        ate_ci_upper = float(ci[1])
    except Exception:
        logger.debug(
            "LinearDML estimation failed for %s -> %s",
            treatment_name,
            outcome_name,
            exc_info=True,
        )
        return None

    # P-value from inference (if available).
    ate_p_value = None
    try:
        inference = dml.effect_inference()
        pvals = inference.pvalue()
        ate_p_value = float(np.mean(pvals))
    except Exception:
        pass

    ci_excludes_zero = (ate_ci_lower > 0 and ate_ci_upper > 0) or (
        ate_ci_lower < 0 and ate_ci_upper < 0
    )

    # -- Refutation tests ------------------------------------------------
    placebo_passed = _run_refutation_placebo_dml(
        Y, T, confounders, ate, n
    )
    random_cause_passed = _run_refutation_random_common_cause_dml(
        Y, T, confounders, ate, n
    )
    subset_passed = _run_refutation_subset_dml(
        Y, T, confounders, ate, n
    )

    all_passed = placebo_passed and random_cause_passed and subset_passed

    return CausalResult(
        treatment_metric=treatment_name,
        outcome_metric=outcome_name,
        lag_days=0,
        estimator="LinearDML",
        ate=ate,
        ate_ci_lower=ate_ci_lower,
        ate_ci_upper=ate_ci_upper,
        ate_p_value=ate_p_value,
        placebo_treatment_passed=placebo_passed,
        random_common_cause_passed=random_cause_passed,
        subset_passed=subset_passed,
        all_refutations_passed=all_passed,
        ci_excludes_zero=ci_excludes_zero,
        n_samples=n,
    )


# ---------------------------------------------------------------------------
# Refutation helpers
# ---------------------------------------------------------------------------


def _run_refutation_placebo_dml(
    Y: "np.ndarray",
    T: "np.ndarray",
    W: "np.ndarray | None",
    original_ate: float,
    n: int,
) -> bool:
    """Placebo treatment: permute treatment and re-estimate.

    Passes when the placebo ATE is near zero (the effect vanishes with
    randomized treatment assignment).
    """
    import numpy as np

    try:
        from econml.dml import LinearDML
        from sklearn.ensemble import GradientBoostingRegressor

        rng = np.random.default_rng(0)
        placebo_ates = []
        for _ in range(REFUTATION_PLACEBO_NUM_SIMULATIONS):
            T_perm = rng.permutation(T, axis=0)
            dml = LinearDML(
                model_y=GradientBoostingRegressor(n_estimators=30, max_depth=2),
                model_t=GradientBoostingRegressor(n_estimators=30, max_depth=2),
                discrete_treatment=False,
            )
            dml.fit(Y, T_perm, W=W)
            placebo_ates.append(float(dml.ate()))

        # Placebo effect should be near zero.
        mean_placebo = float(np.mean(placebo_ates))
        return abs(mean_placebo) < abs(original_ate) * 0.5
    except Exception:
        logger.debug("Placebo refutation failed", exc_info=True)
        return False


def _run_refutation_random_common_cause_dml(
    Y: "np.ndarray",
    T: "np.ndarray",
    W: "np.ndarray | None",
    original_ate: float,
    n: int,
) -> bool:
    """Random common cause: add a random confounder and re-estimate.

    Passes when the ATE doesn't change significantly (within 30%).
    """
    import numpy as np

    try:
        from econml.dml import LinearDML
        from sklearn.ensemble import GradientBoostingRegressor

        rng = np.random.default_rng(0)
        random_confounder = rng.normal(0, 1, size=(n, 1))
        if W is not None:
            W_augmented = np.hstack([W, random_confounder])
        else:
            W_augmented = random_confounder

        dml = LinearDML(
            model_y=GradientBoostingRegressor(n_estimators=50, max_depth=3),
            model_t=GradientBoostingRegressor(n_estimators=50, max_depth=3),
            discrete_treatment=False,
        )
        dml.fit(Y, T, W=W_augmented)
        new_ate = float(dml.ate())

        # Effect should stay within 30% of original.
        if abs(original_ate) < 1e-8:
            return abs(new_ate) < 0.1
        ratio = abs(new_ate / original_ate)
        return 0.7 <= ratio <= 1.3
    except Exception:
        logger.debug("Random common cause refutation failed", exc_info=True)
        return False


def _run_refutation_subset_dml(
    Y: "np.ndarray",
    T: "np.ndarray",
    W: "np.ndarray | None",
    original_ate: float,
    n: int,
) -> bool:
    """Subset: re-estimate on 80% of data.

    Passes when the subset ATE is close to the full-data ATE (within 30%).
    """
    import numpy as np

    try:
        from econml.dml import LinearDML
        from sklearn.ensemble import GradientBoostingRegressor

        rng = np.random.default_rng(0)
        mask = rng.random(n) < REFUTATION_SUBSET_FRACTION
        if mask.sum() < MIN_OBSERVATIONS:
            return False

        T_sub = T[mask]
        Y_sub = Y[mask]
        W_sub = W[mask] if W is not None else None

        dml = LinearDML(
            model_y=GradientBoostingRegressor(n_estimators=50, max_depth=3),
            model_t=GradientBoostingRegressor(n_estimators=50, max_depth=3),
            discrete_treatment=False,
        )
        dml.fit(Y_sub, T_sub, W=W_sub)
        new_ate = float(dml.ate())

        # Effect should stay within 30% of original.
        if abs(original_ate) < 1e-8:
            return abs(new_ate) < 0.1
        ratio = abs(new_ate / original_ate)
        return 0.7 <= ratio <= 1.3
    except Exception:
        logger.debug("Subset refutation failed", exc_info=True)
        return False


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


async def persist_causal_results(
    db: "AsyncSession",
    user_id: str,
    results: list[CausalResult],
) -> tuple[int, int]:
    """Write results to ``ml_causal_estimates`` and update ``UserCorrelation``.

    Returns (rows_written, correlations_updated).
    """
    from app.core.time import utcnow_naive
    from app.models.correlation import UserCorrelation
    from app.models.ml_discovery import MLCausalEstimate

    now = utcnow_naive()
    rows_written = 0
    correlations_updated = 0

    for r in results:
        db.add(
            MLCausalEstimate(
                user_id=user_id,
                treatment_metric=r.treatment_metric,
                outcome_metric=r.outcome_metric,
                lag_days=r.lag_days,
                estimator=r.estimator,
                ate=r.ate,
                ate_ci_lower=r.ate_ci_lower,
                ate_ci_upper=r.ate_ci_upper,
                ate_p_value=r.ate_p_value,
                placebo_treatment_passed=r.placebo_treatment_passed,
                random_common_cause_passed=r.random_common_cause_passed,
                subset_passed=r.subset_passed,
                all_refutations_passed=r.all_refutations_passed,
                ci_excludes_zero=r.ci_excludes_zero,
                n_samples=r.n_samples,
                model_version=MODEL_VERSION,
                computed_at=now,
            )
        )
        rows_written += 1

        # Promote to causal_candidate when CI excludes zero AND all refuters pass.
        if r.all_refutations_passed and r.ci_excludes_zero:
            existing = await db.execute(
                select(UserCorrelation).where(
                    UserCorrelation.user_id == user_id,
                    UserCorrelation.source_metric == r.treatment_metric,
                    UserCorrelation.target_metric == r.outcome_metric,
                    UserCorrelation.lag_days == r.lag_days,
                )
            )
            record = existing.scalar_one_or_none()
            if record is not None:
                record.causal_support = True
                record.confidence_tier = "causal_candidate"
                record.last_validated_at = now
                correlations_updated += 1

    await db.flush()
    return rows_written, correlations_updated


# ---------------------------------------------------------------------------
# User-level orchestrator
# ---------------------------------------------------------------------------


async def run_causal_for_user(
    db: "AsyncSession",
    user_id: str,
    window_days: int = 90,
    max_pairs: int = 10,
) -> CausalReport:
    """Run L4 quasi-causal estimation on eligible pairs for a user.

    Eligible pairs are those with ``directional_support=True`` or
    ``literature_match=True``. Tests the top ``max_pairs`` by strength.

    Does NOT commit. Caller owns the transaction.
    """
    import time

    import numpy as np

    from ml.features.store import get_feature_frame
    from app.models.correlation import UserCorrelation

    report = CausalReport(user_id=user_id)

    # 1. Load eligible pairs (directional_support OR literature_match).
    t0 = time.perf_counter()
    stmt = (
        select(UserCorrelation)
        .where(
            UserCorrelation.user_id == user_id,
            (UserCorrelation.directional_support == True)  # noqa: E712
            | (UserCorrelation.literature_match == True),  # noqa: E712
        )
        .order_by(UserCorrelation.strength.desc())
        .limit(max_pairs)
    )
    result = await db.execute(stmt)
    pairs = result.scalars().all()
    report.timings_ms["load_pairs"] = (time.perf_counter() - t0) * 1000

    if not pairs:
        logger.info("run_causal_for_user(%s): no eligible pairs, skipping", user_id)
        return report

    # 2. Collect features.
    feature_keys: set[str] = set()
    for p in pairs:
        feature_keys.add(p.source_metric)
        feature_keys.add(p.target_metric)

    # 3. Pull feature frame.
    t0 = time.perf_counter()
    today = date.today()
    start = today - timedelta(days=window_days)
    frame = await get_feature_frame(
        db,
        user_id,
        feature_keys=sorted(feature_keys),
        start=start,
        end=today,
        include_imputed=False,
    )
    report.timings_ms["feature_fetch"] = (time.perf_counter() - t0) * 1000

    # 4. Run causal estimation for each pair.
    t0 = time.perf_counter()
    causal_results: list[CausalResult] = []
    for p in pairs:
        src_col = p.source_metric
        tgt_col = p.target_metric

        if src_col not in frame.columns or tgt_col not in frame.columns:
            report.pairs_skipped_insufficient_data += 1
            continue

        # Build aligned arrays (drop NaN rows).
        pair_df = frame[[src_col, tgt_col]].dropna()
        if len(pair_df) < MIN_OBSERVATIONS:
            report.pairs_skipped_insufficient_data += 1
            continue

        treatment = pair_df[src_col].values.astype(np.float64)
        outcome = pair_df[tgt_col].values.astype(np.float64)

        # Use any other available features as confounders.
        other_cols = [c for c in frame.columns if c not in (src_col, tgt_col)]
        confounders = None
        if other_cols:
            conf_df = frame.loc[pair_df.index, other_cols].fillna(0.0)
            confounders = conf_df.values.astype(np.float64)

        cr = _estimate_causal_effect(
            treatment, outcome, confounders, src_col, tgt_col
        )
        if cr is None:
            report.pairs_estimation_failed += 1
            continue

        cr.lag_days = p.lag_days
        report.pairs_tested += 1
        causal_results.append(cr)

        if cr.all_refutations_passed and cr.ci_excludes_zero:
            report.pairs_passed += 1

    report.timings_ms["causal_compute"] = (time.perf_counter() - t0) * 1000

    # 5. Persist.
    t0 = time.perf_counter()
    rows, updated = await persist_causal_results(db, user_id, causal_results)
    report.rows_written = rows
    report.correlations_updated = updated
    report.timings_ms["persist"] = (time.perf_counter() - t0) * 1000

    logger.info(
        "run_causal_for_user(%s): tested=%d passed=%d failed=%d "
        "skipped_data=%d rows=%d updated=%d",
        user_id,
        report.pairs_tested,
        report.pairs_passed,
        report.pairs_estimation_failed,
        report.pairs_skipped_insufficient_data,
        report.rows_written,
        report.correlations_updated,
    )
    return report
