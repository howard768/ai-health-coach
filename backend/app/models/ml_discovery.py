"""Schema for Signal Engine Phase 6 tables: L3 Granger + L4 DoWhy.

Two new ML tables, both prefixed ``ml_`` per the plan. Written by
``backend/ml/discovery/granger.py`` and ``backend/ml/discovery/causal.py``.
Read only by ``backend/ml/`` modules (boundary test enforces it).

Tables:

- ``ml_directional_tests`` -- one row per Granger causality test attempt.
  Records stationarity check, differencing order applied, F-statistic,
  p-value, and whether the test reached significance (p < 0.05).
- ``ml_causal_estimates`` -- one row per DoWhy quasi-causal estimation.
  Records ATE with CI, and pass/fail for each of the three refutation
  tests (placebo treatment, random common cause, subset data).

See ``~/.claude/plans/golden-floating-creek.md`` Phase 6 for the full spec.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow_naive
from app.database import Base


class MLDirectionalTest(Base):
    """One Granger causality test attempt on a (source, target, lag) pair.

    Written by L3 for every ``developing+`` pair from ``UserCorrelation``.
    A ``significant=True`` row means L3 found Granger-causal evidence at
    the 0.05 threshold; the pipeline then sets ``directional_support=True``
    on the corresponding ``UserCorrelation`` row.
    """

    __tablename__ = "ml_directional_tests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    source_metric: Mapped[str] = mapped_column(String(100))
    target_metric: Mapped[str] = mapped_column(String(100))
    lag_days: Mapped[int] = mapped_column(Integer, nullable=False)
    is_stationary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        doc="True if ADF rejects unit root at 5% on the raw series (no differencing needed).",
    )
    differencing_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="0 = tested on levels, 1 = first-differenced. Higher orders not attempted.",
    )
    f_statistic: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        doc="Best F-statistic across tested lags. None if stationarity gate failed.",
    )
    p_value: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        doc="P-value corresponding to the best F-statistic. None if stationarity gate failed.",
    )
    max_lag_tested: Mapped[int] = mapped_column(Integer, nullable=False)
    optimal_lag: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Lag order that produced the best F-stat. None if stationarity gate failed.",
    )
    significant: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        doc="True when p_value < 0.05 AND the pair was stationary (possibly after differencing).",
    )
    model_version: Mapped[str] = mapped_column(String(40), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow_naive, nullable=False
    )


class MLCausalEstimate(Base):
    """One DoWhy quasi-causal estimation for a (treatment, outcome) pair.

    Written by L4 for pairs that have ``directional_support=True`` or
    ``literature_match=True``. A row where ``all_refutations_passed=True``
    AND ``ci_excludes_zero=True`` is eligible for the
    ``causal_candidate`` confidence tier.
    """

    __tablename__ = "ml_causal_estimates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    treatment_metric: Mapped[str] = mapped_column(String(100))
    outcome_metric: Mapped[str] = mapped_column(String(100))
    lag_days: Mapped[int] = mapped_column(Integer, nullable=False)
    estimator: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        doc='"DML" (econml.dml.DML). Future: could support other estimators.',
    )
    ate: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        doc="Average Treatment Effect point estimate.",
    )
    ate_ci_lower: Mapped[float | None] = mapped_column(Float, nullable=True)
    ate_ci_upper: Mapped[float | None] = mapped_column(Float, nullable=True)
    ate_p_value: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        doc="Two-sided p-value for ATE != 0, if available from the estimator.",
    )
    placebo_treatment_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    random_common_cause_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    subset_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    all_refutations_passed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        doc="True only when all three refuters pass. Logical AND of the three bools above.",
    )
    ci_excludes_zero: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        doc="True when the 95% CI for ATE does not contain zero.",
    )
    n_samples: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Number of aligned (treatment, outcome) observations used.",
    )
    model_version: Mapped[str] = mapped_column(String(40), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow_naive, nullable=False
    )
