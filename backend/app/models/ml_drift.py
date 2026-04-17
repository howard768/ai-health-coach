"""Schema for per-feature drift results populated by ``synth_drift_job``.

One table:

- ``ml_drift_results`` -- one row per ``(synth_run_id, feature_key)``
  produced by a single drift-monitoring run. Records the KS statistic,
  the p-value, the active threshold at the time of the run, and the
  resulting ``drifted`` flag. Stored so ``/ops/ml/feature-drift`` can
  surface the latest snapshot without recomputing, and so the
  meld-feature-drift scheduled task can file real Linear issues when
  drift exceeds the rule.

The ``synth_run_id`` links back to ``ml_synth_runs.run_id`` when the
drift run was produced from a synth cohort, but the column is not a
hard FK: the drift job also runs outside of a synth-generation
transaction, and in that case the id is the drift run's own uuid.
Keeping it string-keyed without a referential constraint keeps the
table independent and mirrors the pattern used by ``ml_synth_runs``.

Threshold is stored per row so historical drift judgments remain
stable even when the rule changes. The Phase 4.5 plan specifies a
KS-statistic cutoff of 0.15: rows with ``ks_statistic > 0.15`` are
flagged drifted. This is a more durable decision than the
p-value-based rule used inline by ``ml.mlops.evidently_reports``,
which can shift with scipy's small-sample approximations.

Lives under ``app/models/`` for alembic discovery; read and written
only from ``backend/ml/`` code (boundary test enforces it). No PHI:
the ``feature_key`` column is a metric identifier
(``hrv``, ``sleep_efficiency``, ...), not a user id.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow_naive
from app.database import Base


class MLDriftResult(Base):
    """One drift-stat row: one feature's KS result in one drift run.

    Write-once per ``(synth_run_id, feature_key)`` tuple. The drift
    job writes N rows (one per feature tested) in the same transaction
    as the surrounding ``ml_synth_runs`` row so the manifest and the
    per-feature judgments stay in sync.
    """

    __tablename__ = "ml_drift_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    synth_run_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
        doc=(
            "Links back to the drift run id. When the drift run was triggered "
            "from a synth cohort generation, this equals ml_synth_runs.run_id; "
            "when triggered standalone by the scheduler, this is the drift "
            "run's own uuid4 hex. Not a hard FK so the table stays "
            "independent of synth-generation lifecycle."
        ),
    )
    feature_key: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        index=True,
        doc="Metric identifier (e.g., 'hrv', 'sleep_efficiency'). Never user-identifying.",
    )
    ks_statistic: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        doc="Two-sample Kolmogorov-Smirnov D statistic (0..1, larger means more drift).",
    )
    ks_pvalue: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        doc="P-value from the KS test. Preserved for audit but not the drift decision.",
    )
    threshold: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        doc=(
            "KS-statistic cutoff in force when this row was written (Phase 4.5 "
            "plan: 0.15). Stored per row so historical judgments stay stable "
            "if the global rule changes later."
        ),
    )
    drifted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        doc="True iff ks_statistic > threshold at write time.",
    )
    sample_size_real: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Non-null observations on the reference (is_synthetic=False) side.",
    )
    sample_size_synth: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Non-null observations on the current (is_synthetic=True) side.",
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow_naive,
        nullable=False,
        index=True,
        doc="Write timestamp. Endpoint picks the batch with MAX(computed_at).",
    )

    __table_args__ = (
        # Composite index accelerates "pick the most recent synth_run_id
        # then fetch its per-feature rows" lookups.
        Index("ix_ml_drift_results_run_feature", "synth_run_id", "feature_key"),
    )
