"""Schema for Signal Engine Phase 8 cross-user cohort tables.

Three tables for opt-in anonymized clustering:

- ``ml_cohort_consent`` -- per-user opt-in lifecycle. Primary key is user_id.
  Tracks opt-in, opt-out, deletion request, and deletion completion timestamps.
- ``ml_anonymized_vectors`` -- pseudonymized (HMAC-SHA256) and DP-noised
  pattern vectors. user_id_encrypted is for deletion lookup only; the
  clustering pipeline only sees pseudonym_id + vector.
- ``ml_cohorts`` -- one row per cluster per monthly run. Deactivated on
  the next run. Archetype name/description assigned by the narrator.

Privacy invariants:
- ml_anonymized_vectors NEVER contains raw user_ids.
- Vectors have Laplace DP noise (epsilon=1.0) applied BEFORE storage.
- Clusters enforce k-anonymity >= 50 (HDBSCAN min_cluster_size).

See ``~/.claude/plans/golden-floating-creek.md`` Phase 8 for the full spec.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow_naive
from app.database import Base


class MLCohortConsent(Base):
    """Per-user opt-in status for cross-user cohort clustering.

    Primary key is user_id (one consent record per user, ever).
    Opt-in and opt-out are timestamped independently so we can track
    the full lifecycle for GDPR audit.
    """

    __tablename__ = "ml_cohort_consent"

    user_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    opted_in: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    opted_in_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    opted_out_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deletion_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        doc="When the user requested deletion of their anonymized vectors.",
    )
    deletion_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        doc="When the deletion was completed. Must be within 30 days of request.",
    )


class MLAnonymizedVector(Base):
    """Pseudonymized, DP-noised pattern vector for one user.

    The pseudonym_id is HMAC-SHA256(user_id, rotating_monthly_key).
    user_id_encrypted is stored only for deletion lookup (when a user
    opts out, we need to find and delete their vector). The clustering
    pipeline only sees pseudonym_id + vector.
    """

    __tablename__ = "ml_anonymized_vectors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pseudonym_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
        doc="HMAC-SHA256(user_id, rotating_key). Changes monthly.",
    )
    user_id_encrypted: Mapped[str] = mapped_column(
        String(255),
        index=True,
        nullable=False,
        doc="Encrypted user_id for deletion lookup. NOT the raw user_id.",
    )
    vector_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="JSON array of floats. DP-noised pattern vector.",
    )
    feature_names_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="JSON array of feature names in vector order.",
    )
    dp_epsilon: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        doc="Epsilon used for Laplace DP noise on this vector.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow_naive, nullable=False
    )


class MLCohort(Base):
    """One cluster from a monthly HDBSCAN run.

    Multiple rows per run_id (one per cluster). Previous run deactivated
    when a new run completes. Archetype name and description are assigned
    post-clustering by the narrator (Phase 8B).
    """

    __tablename__ = "ml_cohorts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cluster_label: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="HDBSCAN cluster label (0-indexed). -1 = noise (not stored).",
    )
    n_members: Mapped[int] = mapped_column(Integer, nullable=False)
    centroid_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="JSON array of floats. Mean of all member vectors in this cluster.",
    )
    archetype_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="Human-readable archetype name, e.g. 'Active Sleepers'. Assigned by narrator.",
    )
    archetype_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Plain-language description of this archetype's distinguishing features.",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="True for the current run's clusters. Previous run deactivated.",
    )
    run_id: Mapped[str] = mapped_column(
        String(36),
        index=True,
        nullable=False,
        doc="UUID of the clustering run. Links all clusters from one run.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow_naive, nullable=False
    )
