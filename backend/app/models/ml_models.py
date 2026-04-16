"""Schema for Signal Engine Phase 7 model registry.

One table:

- ``ml_models`` -- one row per trained model artifact. Tracks type (e.g.
  "ranker"), version string, file hash for conditional download, R2 storage
  key, and training metadata (samples, validation NDCG, feature names,
  hyperparameters).

The ``is_active`` flag determines which model version is currently served.
Only one model per type should be active at a time; the trainer deactivates
the previous version before activating the new one.

Like every other ml_ table, lives under ``app/models/`` for alembic
discovery and is read/written only from ``backend/ml/`` code (boundary
test enforces it).
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow_naive
from app.database import Base


class MLModel(Base):
    """Registry row for one trained model artifact.

    Written by the training pipeline (``ml.ranking.trainer`` for ranker
    models). Read by ``ml.api.ranker_model_metadata()`` to serve the
    iOS download endpoint.
    """

    __tablename__ = "ml_models"
    __table_args__ = (
        UniqueConstraint(
            "model_type",
            "model_version",
            name="uq_ml_models_type_version",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_type: Mapped[str] = mapped_column(
        String(40),
        index=True,
        nullable=False,
        doc='"ranker" for XGBoost LambdaMART. Future: "forecaster", "anomaly_detector".',
    )
    model_version: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        doc="Semantic version, e.g. ranker-1.0.0. Bumped on every retrain.",
    )
    file_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        doc="SHA-256 hex of the CoreML .mlmodel file. Used for conditional download.",
    )
    file_size_bytes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Size of the CoreML .mlmodel file in bytes.",
    )
    r2_key: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Cloudflare R2 object key, e.g. coreml/ranker-1.0.0.mlmodel.",
    )
    download_url: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        doc="Public download URL (R2 custom domain or signed URL).",
    )
    train_samples: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Number of labeled pairs used for training.",
    )
    val_ndcg: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        doc="Validation NDCG@5 from the train/val split.",
    )
    feature_names_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="JSON array of feature names in model input order.",
    )
    hyperparams_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="JSON dict of XGBoost hyperparameters used for training.",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="True for the currently served model. Only one per model_type should be active.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow_naive, nullable=False
    )
    rolled_back_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        doc="Timestamp when this model was rolled back to (re-activated after deactivation).",
    )
