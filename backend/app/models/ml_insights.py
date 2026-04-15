"""Schema for Signal Engine Phase 4 — insight candidates + rankings.

Two tables:

- ``ml_insight_candidates`` — one row per surfaceable finding, regardless of
  kind (correlation, anomaly, forecast_warning, etc.). Normalized into a
  common shape so the ranker sees apples-to-apples.
- ``ml_rankings`` — per-(user, date) ranked slate. Only rank=1 is displayed;
  rank 2+ are kept for shadow-mode comparison and for training the learned
  ranker in Phase 7. ``was_shown`` and ``feedback`` close the user feedback
  loop.

Like every other ml_ table, both live under ``app/models/`` for alembic
discovery and are read/written only from ``backend/ml/`` code.
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


class MLInsightCandidate(Base):
    """One surfaceable finding, normalized into the shape the ranker consumes.

    ``id`` is a deterministic hash of (user_id, kind, canonical subject).
    Rerunning candidate generation on the same day produces the same ids,
    so rankings can reference them stably. ``payload_json`` carries the
    kind-specific context the narrator / explainer needs (correlation row
    id, anomaly residual, forecast target date, etc.).
    """

    __tablename__ = "ml_insight_candidates"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(
        String(40),
        index=True,
        nullable=False,
        doc="correlation | anomaly | forecast_warning | experiment_result | streak | regression",
    )
    subject_metrics_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="JSON array of feature keys the candidate is about.",
    )

    effect_size: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        doc="0-1 normalized (abs(r) for correlations, |z| / 5 for anomalies clamped to 1).",
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        doc="0-1 from tier: emerging=0.3, developing=0.6, established=0.8, causal_candidate=0.9, literature_supported=0.95.",
    )
    novelty: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        doc="1 - cosine similarity against candidates surfaced to this user in the last 30 days.",
    )
    recency_days: Mapped[int] = mapped_column(Integer, nullable=False)
    actionability_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        doc="0-1. Rule-based: modifiable source features (dinner_hour, protein, steps, workouts) score higher than biometrics.",
    )
    literature_support: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    directional_support: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    causal_support: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    payload_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Kind-specific context. Correlation: source/target/lag/pearson_r. Anomaly: observation_date/residual/z. Forecast: target_date/y_hat.",
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow_naive, nullable=False
    )


class MLRanking(Base):
    """Per-(user, surface_date) ranked slate.

    One row per ranked position. ``rank=1`` is the card we actually show;
    rank 2+ are kept for shadow comparison, A/B, and Phase 7 ranker
    training data. Feedback fields close the loop.
    """

    __tablename__ = "ml_rankings"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "surface_date",
            "rank",
            "ranker_version",
            name="uq_ml_rankings_user_date_rank_version",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    surface_date: Mapped[str] = mapped_column(
        String(10),
        index=True,
        nullable=False,
        doc="YYYY-MM-DD. Day the card was (or would have been) shown.",
    )
    candidate_id: Mapped[str] = mapped_column(
        String(64),
        index=True,
        nullable=False,
        doc="FK-ish pointer to ml_insight_candidates.id (not a hard FK so we can purge candidates independently).",
    )
    rank: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="1-indexed. Only rank=1 is shown. 2+ kept for shadow logging.",
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    heuristic_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        doc="Phase 7 A/B: heuristic ranker score for this candidate. "
        "When a learned model is active, ``score`` holds the learned score "
        "and ``heuristic_score`` holds the heuristic for shadow comparison.",
    )
    ranker_version: Mapped[str] = mapped_column(String(40), nullable=False)

    was_shown: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="Flipped true when iOS renders the card. Used for cap enforcement and feedback attribution.",
    )
    shown_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    feedback: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        doc="thumbs_up | thumbs_down | dismissed | already_knew | null.",
    )
    feedback_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow_naive, nullable=False
    )
