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

    Phase 2 implements L1 only (baselines + change points + forecasts + anomaly
    detection). Phase 3 adds L2 associations, Phase 6 adds L3 Granger + L4
    DoWhy, Phase 9 adds L5 APTE.

    Does NOT commit — caller owns the transaction.
    """
    from datetime import date, datetime, timezone

    # Lazy imports per boundary rules + cold-boot budget.
    from ml.discovery.baselines import compute_baselines_for_user
    from ml.forecasting.anomaly import detect_anomalies_for_user
    from ml.forecasting.residuals import compute_forecasts_for_user

    started = datetime.now(timezone.utc).isoformat()
    through_date = date.today()
    layers_run: list[str] = []
    tier_counts: dict[str, int] = {}

    # L1 baselines + change points.
    baseline_run = await compute_baselines_for_user(db, user_id, through_date)
    layers_run.append("baselines")
    tier_counts["baselines_written"] = baseline_run.baselines_written
    tier_counts["change_points_written"] = baseline_run.change_points_written

    # Forecasts for the next 7 days.
    forecasts = await compute_forecasts_for_user(db, user_id, made_on=through_date)
    layers_run.append("forecasts")
    tier_counts["forecast_metrics"] = len(forecasts)

    # Residual anomaly detection over the last week.
    anomaly_run = await detect_anomalies_for_user(db, user_id, through_date)
    layers_run.append("anomalies")
    tier_counts["anomalies_written"] = anomaly_run.anomalies_written

    return DiscoveryReport(
        user_id=user_id,
        run_started_at=started,
        run_finished_at=datetime.now(timezone.utc).isoformat(),
        layers_run=layers_run,
        patterns_tested=baseline_run.baselines_written,
        patterns_surfaced=0,  # Phase 2 is shadow-only; nothing is surfaced.
        tier_counts=tier_counts,
        shadow_mode=True,
    )


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
    """Return the most recent ensembled forecast for ``metric``.

    Reads from ``ml_forecasts`` populated by the nightly ``baselines_job``.
    Returns a Forecast with empty ``points`` if no forecast has been
    computed yet. On-demand computation is intentionally not supported:
    Prophet is too expensive to run synchronously in the request path.
    """
    from datetime import date as _date
    from datetime import timedelta

    from sqlalchemy import select

    # Lazy import to keep api.py light.
    from app.models.ml_baselines import MLForecast

    today = _date.today()
    start = today + timedelta(days=1)
    end = today + timedelta(days=horizon_days)

    result = await db.execute(
        select(MLForecast)
        .where(
            MLForecast.user_id == user_id,
            MLForecast.metric_key == metric,
            MLForecast.target_date >= start.isoformat(),
            MLForecast.target_date <= end.isoformat(),
        )
        .order_by(MLForecast.target_date.asc(), MLForecast.made_on.desc())
    )
    rows = list(result.scalars().all())

    # Keep the most recent made_on per target_date.
    seen_targets: set[str] = set()
    points: list[dict[str, object]] = []
    made_on_latest: str | None = None
    model_version: str | None = None
    for row in rows:
        if row.target_date in seen_targets:
            continue
        seen_targets.add(row.target_date)
        points.append(
            {
                "date": row.target_date,
                "y_hat": row.y_hat,
                "y_hat_low": row.y_hat_low,
                "y_hat_high": row.y_hat_high,
            }
        )
        if made_on_latest is None or row.made_on > made_on_latest:
            made_on_latest = row.made_on
        model_version = row.model_version

    return Forecast(
        user_id=user_id,
        metric=metric,
        horizon_days=horizon_days,
        points=points,
        model_version=model_version or "",
        made_on=made_on_latest or "",
    )


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


@dataclass
class AssociationsReport:
    """Phase 3 L2 output summary. Shape mirrors the internal report from
    ``ml.discovery.associations`` so callers (scheduler, tests) see a stable
    shape across the public boundary.
    """

    user_id: str
    window_days: int
    pairs_tested: int
    pairs_with_enough_data: int
    significant_results: int
    dynamic_pairs_generated: int
    rows_written: int


async def run_associations(
    db: "AsyncSession",
    user_id: str,
    window_days: int = 30,
) -> AssociationsReport:
    """Run L2 associations: dual-method correlations + BH-FDR + persistence.

    Replaces the direct call to
    ``backend/app/services/correlation_engine.compute_correlations`` in the
    scheduler. Reads the Phase 1 feature store (features must be fresh;
    scheduler orders ``feature_refresh_job`` at 03:30 UTC before
    ``correlation_engine_job``).

    Writes to ``UserCorrelation`` with legacy-compatible ``source_metric``
    and ``target_metric`` strings so downstream code that reads those fields
    keeps working without a rename migration.

    Does NOT commit — caller owns the transaction.
    """
    # Lazy import per boundary rules + cold-boot budget.
    from ml.discovery.associations import run_associations_for_user

    report = await run_associations_for_user(db, user_id, window_days=window_days)
    return AssociationsReport(
        user_id=report.user_id,
        window_days=report.window_days,
        pairs_tested=report.pairs_tested,
        pairs_with_enough_data=report.pairs_with_enough_data,
        significant_results=report.significant_results,
        dynamic_pairs_generated=report.dynamic_pairs_generated,
        rows_written=report.rows_written,
    )
