"""Schema for Signal Engine Phase 4.5, Commit 6, synth cohort manifests.

One table:

- ``ml_synth_runs`` -- one row per ``ml.api.generate_synth_cohort`` call.
  Records which users were created, what seed produced them, and over
  which date window, so a later audit can explain why a given batch of
  ``is_synthetic=True`` rows exists in the raw tables.

The ``run_id`` matches the ``uuid4`` hex already emitted by
``factory.generate_cohort`` and stamped on the returned
``CohortManifest``. Keeping the primary key identical to the manifest's
``run_id`` means a scheduler job can log a single uuid and any operator
can cross-reference it to both the DB row and the returned dataclass
without a lookup table.

Like every other ml_ table, lives under ``app/models/`` for alembic
discovery and is read/written only from ``backend/ml/`` code (boundary
test enforces it).
"""

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MLSynthRun(Base):
    """Audit row for one synthesis run.

    Write-once per cohort. The factory writes this row in the same
    transaction as the raw-table rows so the manifest and the data
    stay in sync, even if the caller rolls back.
    """

    __tablename__ = "ml_synth_runs"

    # uuid4 hex (32 chars) or uuid4 with dashes (36). Factory emits hex
    # (no dashes) via ``uuid.uuid4().hex``. Sizing to 36 keeps the
    # column compatible with either format, which saves a migration if
    # the emitter ever flips.
    run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    seed: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Random seed used for the run. NULL for unseeded cohorts.",
    )
    generator: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        doc='"parametric" (scipy + numpy, always) or "gan" (DoppelGANger, extras-gated).',
    )
    n_users: Mapped[int] = mapped_column(Integer, nullable=False)
    days: Mapped[int] = mapped_column(Integer, nullable=False)
    start_date: Mapped[str] = mapped_column(
        String(10), nullable=False, doc="YYYY-MM-DD, cohort window start."
    )
    end_date: Mapped[str] = mapped_column(
        String(10), nullable=False, doc="YYYY-MM-DD, cohort window end."
    )
    created_at: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        doc="ISO-8601 UTC timestamp of the synthesis run.",
    )
    adversarial_fraction: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        doc="Share of conversations seeded with adversarial personas.",
    )
    user_ids_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="JSON-encoded list of synth user_ids produced by this run.",
    )
