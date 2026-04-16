"""Schema for Signal Engine Phase 9 experiment tables.

Two tables for user-initiated n-of-1 personal experiments:

- ``ml_experiments`` -- one row per experiment. Tracks the full lifecycle
  from creation through baseline, washout, treatment, completion, or
  abandonment. Compliance counters track how many days in each phase
  the user actually followed the protocol.
- ``ml_n_of_1_results`` -- one row per completed experiment. Stores the
  APTE estimate, confidence interval, p-value, effect size, and
  compliance metadata.

See ``~/.claude/plans/golden-floating-creek.md`` Phase 9 for the full spec.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow_naive
from app.database import Base


class MLExperiment(Base):
    """One user-initiated personal experiment.

    Status progression for AB design:
    baseline -> washout_1 -> treatment -> analyzing -> completed
    (or -> abandoned at any point)
    """

    __tablename__ = "ml_experiments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    experiment_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        doc="User-visible name, e.g. 'Morning exercise and sleep'.",
    )
    hypothesis: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="User's hypothesis, e.g. 'Exercising before 8am improves my sleep quality'.",
    )
    treatment_metric: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Feature key for the behavior being changed, e.g. 'dinner_hour'.",
    )
    outcome_metric: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Feature key for the outcome being measured, e.g. 'sleep_efficiency'.",
    )
    design: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc='"ab" (14+14 days) or "abab" (4x14 days). MVP uses AB only.',
    )
    baseline_days: Mapped[int] = mapped_column(Integer, nullable=False, default=14)
    treatment_days: Mapped[int] = mapped_column(Integer, nullable=False, default=14)
    washout_days: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    min_compliance: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=10,
        doc="Minimum compliant days per phase before APTE runs.",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="baseline | washout_1 | treatment | analyzing | completed | abandoned",
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    baseline_end: Mapped[str] = mapped_column(
        String(10), nullable=False, doc="YYYY-MM-DD"
    )
    treatment_start: Mapped[str] = mapped_column(
        String(10), nullable=False, doc="YYYY-MM-DD"
    )
    treatment_end: Mapped[str] = mapped_column(
        String(10), nullable=False, doc="YYYY-MM-DD"
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    compliant_days_baseline: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    compliant_days_treatment: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow_naive, nullable=False
    )


class MLNof1Result(Base):
    """APTE result for one completed experiment.

    One row per experiment. Stores the effect estimate, CI, p-value,
    and plain-language metadata for the result card.
    """

    __tablename__ = "ml_n_of_1_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    experiment_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ml_experiments.id"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    treatment_metric: Mapped[str] = mapped_column(String(100), nullable=False)
    outcome_metric: Mapped[str] = mapped_column(String(100), nullable=False)
    apte: Mapped[float | None] = mapped_column(
        Float, nullable=True, doc="Average Period Treatment Effect (mean difference)."
    )
    ci_lower: Mapped[float | None] = mapped_column(Float, nullable=True)
    ci_upper: Mapped[float | None] = mapped_column(Float, nullable=True)
    p_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    effect_size_d: Mapped[float | None] = mapped_column(
        Float, nullable=True, doc="Cohen's d standardized effect size."
    )
    baseline_mean: Mapped[float | None] = mapped_column(Float, nullable=True)
    treatment_mean: Mapped[float | None] = mapped_column(Float, nullable=True)
    baseline_n: Mapped[int] = mapped_column(Integer, nullable=False)
    treatment_n: Mapped[int] = mapped_column(Integer, nullable=False)
    compliant_days_baseline: Mapped[int] = mapped_column(Integer, nullable=False)
    compliant_days_treatment: Mapped[int] = mapped_column(Integer, nullable=False)
    method: Mapped[str] = mapped_column(
        String(40), nullable=False, doc='"permutation_test" for MVP.'
    )
    model_version: Mapped[str] = mapped_column(String(40), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow_naive, nullable=False
    )
