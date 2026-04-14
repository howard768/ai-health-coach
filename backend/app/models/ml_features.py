"""Schema for the Signal Engine feature store.

These ORM classes define the tables that back ``backend.ml.features.store``.
They live under ``app/models/`` because that is where alembic discovers ORM
metadata. The actual read/write behavior lives under ``backend/ml/features/``,
which must be the only code path that touches these tables.

See ``~/.claude/plans/golden-floating-creek.md`` Phase 1 for the full spec.

Design notes:
    - ``feature_date`` is stored as ``String(10)`` (``YYYY-MM-DD``) to match the
      convention used throughout ``health.py`` / ``meal.py``. Keeps joins and
      date-range queries uniform across the ML and non-ML tables without
      per-dialect date-casting.
    - ``(user_id, feature_key, feature_date, feature_version)`` is the natural
      key and enforces idempotent materialization: rerunning the nightly
      feature job on the same day with the same builder version is a no-op.
    - ``feature_version`` is the semver of the *builder*, not the row. When a
      builder changes its math we bump the version and reprocess; old rows
      stay around until a cleanup job removes them.
    - ``is_observed`` separates genuine measurements from imputed / forward-
      filled values. Every downstream model must read this flag and decide
      whether to downweight, skip, or mask imputed rows.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow_naive
from app.database import Base


class MLFeatureValue(Base):
    """A single (user, feature, date, version) materialized value.

    Written by the nightly ``feature_refresh_job`` and read by every
    downstream Signal Engine layer (baselines, associations, forecasting,
    ranking, cohorts). The ``is_observed`` flag and ``_imputed_by`` string
    let callers decide how to treat imputed cells.
    """

    __tablename__ = "ml_feature_values"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "feature_key",
            "feature_date",
            "feature_version",
            name="uq_ml_feature_values_user_key_date_version",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    feature_key: Mapped[str] = mapped_column(String(120), index=True)
    # YYYY-MM-DD to match SleepRecord/HealthMetricRecord convention.
    feature_date: Mapped[str] = mapped_column(String(10), index=True)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_observed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    imputed_by: Mapped[str | None] = mapped_column(
        String(40),
        nullable=True,
        doc="forward_fill, median, population_mean, none. NULL when is_observed=True.",
    )
    source_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        doc="SHA-1 hex of the upstream row ids + values this was built from. Used for cheap cache invalidation.",
    )
    feature_version: Mapped[str] = mapped_column(String(20), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, nullable=False)


class MLFeatureCatalogEntry(Base):
    """Static metadata about each feature.

    Populated idempotently from ``backend.ml.features.catalog`` on each
    nightly materialization run. Provides a single source of truth for what
    features exist, what each one means, what unit it is in, and which
    builder produced it.

    Keeping this in the DB (not just in code) lets downstream services list
    available features without importing ``backend.ml`` directly — which would
    violate the import boundary.
    """

    __tablename__ = "ml_feature_catalog"

    feature_key: Mapped[str] = mapped_column(String(120), primary_key=True)
    category: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        doc="biometric_raw | biometric_derived | activity | nutrition | contextual | data_quality",
    )
    domain: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        doc="sleep | heart | activity | nutrition | engagement | time.",
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    unit: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    builder_module: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Dotted path to the builder function, e.g. ml.features.builders.biometric_raw.",
    )
    current_version: Mapped[str] = mapped_column(String(20), nullable=False)
    requires_features: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="JSON array of feature_keys this derives from. NULL for raw features.",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, nullable=False)
