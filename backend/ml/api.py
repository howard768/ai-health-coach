"""Public API for the Meld Signal Engine.

This module is the **sole** import target allowed from outside ``backend.ml``.
Anything deeper is a boundary violation and will fail
``backend/tests/ml/test_boundary.py``.

All heavy third-party imports (pandas, scipy, statsmodels, xgboost, prophet,
dowhy, econml, shap, mlflow, evidently, nannyml, coremltools) are lazy-imported
inside function bodies. This keeps FastAPI cold boot under the 4-second budget
on Railway. The cold-boot test (``backend/tests/ml/test_cold_boot.py``) enforces
this by measuring import times of the main app.

**Phase 0 status**: every function below is a stub that raises
``NotImplementedError``. Each phase of the rollout will implement these in turn.
See ``~/.claude/plans/golden-floating-creek.md`` for the full plan.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # Type-only imports. Do NOT move out of this block; doing so would
    # trigger heavy sqlalchemy/pydantic chains at module load on cold boot.
    from sqlalchemy.ext.asyncio import AsyncSession


# ─────────────────────────────────────────────────────────────────────────
# Public dataclasses (the shapes the rest of the app is allowed to see).
# These intentionally avoid importing pandas / numpy. Any field that would
# need those types is returned as a plain Python primitive or dict.
# ─────────────────────────────────────────────────────────────────────────


@dataclass
class ActivePattern:
    """A surfaceable cross-domain pattern for one user.

    Replaces the hardcoded ``HealthConnection`` entries in ``coach_engine.py``
    starting in Phase 5. Loaded from ``UserCorrelation`` at ``developing+`` tier.
    """

    source_metric: str
    target_metric: str
    direction: str  # "positive" | "negative"
    strength: float  # 0-1, abs(r)
    confidence_tier: str  # "developing" | "established" | "causal_candidate" | "literature_supported"
    sample_size: int
    effect_description: str  # natural-language, 4th-grade, no em dashes
    literature_ref: str | None = None


@dataclass
class DiscoveryReport:
    """Summary of a single ``run_discovery_pipeline`` invocation."""

    user_id: str
    run_started_at: str  # ISO-8601 UTC
    run_finished_at: str
    layers_run: list[str] = field(default_factory=list)
    patterns_tested: int = 0
    patterns_surfaced: int = 0
    tier_counts: dict[str, int] = field(default_factory=dict)
    shadow_mode: bool = True


@dataclass
class InsightCandidate:
    """Everything the ranker sees. Populated by Phase 4."""

    id: str
    user_id: str
    kind: str  # correlation | anomaly | forecast_warning | experiment_result | streak | regression
    subject_metrics: list[str]
    effect_size: float
    confidence: float
    novelty: float
    recency_days: int
    actionability_score: float
    literature_support: bool = False
    directional_support: bool = False
    causal_support: bool = False
    payload_json: dict[str, Any] = field(default_factory=dict)


@dataclass
class RankedInsight:
    """A candidate after the ranker has scored it."""

    candidate: InsightCandidate
    score: float
    rank: int
    ranker_model_version: str


@dataclass
class InsightExplanation:
    """Response payload for ``/api/coach/explain-finding``.

    ``shap_values`` is a plain list of (feature_name, value) tuples so the
    router can serialize it without pulling pandas/numpy into its import chain.
    """

    insight_id: str
    user_id: str
    explanation_kind: str  # "correlation" | "anomaly" | "forecast_warning"
    top_contributing_features: list[tuple[str, float]] = field(default_factory=list)
    historical_examples: list[dict[str, Any]] = field(default_factory=list)
    shap_values: list[tuple[str, float]] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "insight_id": self.insight_id,
            "user_id": self.user_id,
            "explanation_kind": self.explanation_kind,
            "top_contributing_features": [
                {"feature": name, "value": val}
                for name, val in self.top_contributing_features
            ],
            "historical_examples": self.historical_examples,
            "shap_values": (
                [{"feature": n, "value": v} for n, v in self.shap_values]
                if self.shap_values is not None
                else None
            ),
        }


@dataclass
class Forecast:
    """Short-horizon forecast for a single metric."""

    user_id: str
    metric: str
    horizon_days: int
    points: list[dict[str, Any]] = field(default_factory=list)  # [{date, y_hat, y_hat_low, y_hat_high}]
    model_version: str = ""
    made_on: str = ""  # ISO-8601


@dataclass
class RankerMetadata:
    """Returned by ``ranker_model_metadata()`` for the iOS CoreML sync endpoint."""

    model_version: str
    file_hash: str  # SHA256 of the .mlpackage for conditional GET
    file_size_bytes: int
    download_url: str  # R2 signed URL, valid for TTL
    expires_at: str  # ISO-8601
    min_ios_version: str = "17.0"


@dataclass
class UserContext:
    """Minimal signal passed into ``rank_candidates`` for the server-side path."""

    user_id: str
    current_readiness_bucket: str = "mid"  # "low" | "mid" | "high"
    user_engagement_7d: int = 0
    thumbs_up_rate_30d: float = 0.0


# ─────────────────────────────────────────────────────────────────────────
# Public async interface. Every entry point below is a Phase 0 stub.
# ─────────────────────────────────────────────────────────────────────────


async def refresh_features_for_user(
    db: "AsyncSession",
    user_id: str,
    through_date: date,
    lookback_days: int = 30,
) -> int:
    """Materialize the feature frame for a user through ``through_date``.

    Idempotent: rerunning on the same day with the same builder versions
    recomputes identically. The underlying table enforces
    ``UNIQUE (user_id, feature_key, feature_date, feature_version)``.

    Does NOT commit. The caller owns the transaction (typically the
    scheduler job wraps the call in ``async with db.begin()``).

    Returns the number of rows written to ``ml_feature_values``.
    """
    from datetime import timedelta

    # Lazy import keeps cold-boot under the Railway budget. See
    # ``backend/ml/__init__.py`` for the full rationale.
    from ml.features.store import materialize_for_user

    start = through_date - timedelta(days=lookback_days - 1)
    result = await materialize_for_user(db, user_id, start, through_date)
    return result.rows_written


async def run_discovery_pipeline(
    db: "AsyncSession",
    user_id: str,
) -> DiscoveryReport:
    """Run the full L1 -> L5 discovery pipeline for one user.

    Replaces ``compute_correlations`` from the legacy correlation engine as the
    caller target for ``correlation_engine_job`` in
    ``backend/app/tasks/scheduler.py:433``. Implemented incrementally across
    Phases 2, 3, 6.
    """
    raise NotImplementedError("Phases 2, 3, 6: signal discovery layers")


async def generate_insight_candidates(
    db: "AsyncSession",
    user_id: str,
) -> list[InsightCandidate]:
    """Normalize all surfaceable findings into ``InsightCandidate`` objects.

    Reads from ``UserCorrelation`` (developing+ tier), ``ml_anomalies``,
    ``ml_forecasts`` (warnings), ``ml_n_of_1_results``. Implemented in Phase 4.
    """
    raise NotImplementedError("Phase 4: candidate normalization")


async def rank_candidates(
    candidates: list[InsightCandidate],
    user_context: UserContext,
) -> list[RankedInsight]:
    """Score + order candidates. Heuristic ranker in Phase 4, learned in Phase 7.

    This is the **server-side** rank path (used e.g. for notification content
    selection). The iOS client runs its own CoreML copy on device for the
    dashboard card ordering. Both paths must stay within the per-day and
    per-week exposure caps defined in ``MLSettings``.
    """
    raise NotImplementedError("Phase 4 (heuristic), Phase 7 (learned)")


async def explain_insight(
    db: "AsyncSession",
    user_id: str,
    insight_id: str,
) -> InsightExplanation:
    """Build a SHAP-backed explanation for a given insight.

    Called by ``/api/coach/explain-finding`` in Phase 5. Dispatches by
    candidate kind: correlation explanations return the correlation itself;
    anomaly + forecast_warning kinds run SHAP on a surrogate residual model.
    """
    raise NotImplementedError("Phase 5: SHAP-backed explanation")


async def forecast_metric(
    db: "AsyncSession",
    user_id: str,
    metric: str,
    horizon_days: int = 7,
) -> Forecast:
    """Return the ensembled (seasonal-naive + Prophet) short-horizon forecast.

    Implemented in Phase 2. Stored results are read-through cached in
    ``ml_forecasts``; a cache miss triggers an on-demand compute.
    """
    raise NotImplementedError("Phase 2: forecasting ensemble")


async def load_active_patterns(
    db: "AsyncSession",
    user_id: str,
) -> list[ActivePattern]:
    """Top-5 developing+ patterns for this user, natural-language rendered.

    **Replaces** the hardcoded ``KnowledgeGraph`` seeded at
    ``backend/app/services/coach_engine.py:195-222``. Implemented in Phase 5.
    Until then, ``coach_engine`` continues to use its internal seed.
    """
    raise NotImplementedError("Phase 5: UserCorrelation-backed active patterns")


def ranker_model_metadata() -> RankerMetadata:
    """Current CoreML ranker metadata for the iOS sync endpoint.

    Implemented in Phase 7. iOS uses the returned hash to decide whether to
    re-download the ``.mlpackage`` on wifi. Synchronous because the iOS client
    polls it on every app launch.
    """
    raise NotImplementedError("Phase 7: CoreML ranker metadata")
