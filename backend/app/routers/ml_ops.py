"""Read-only ML ops endpoints for Phase 5 scheduled-task consumption.

Surfaces aggregate signal-quality, data-quality, drift, experiment, retrain,
and model-registry state for autonomous monitoring loops. All endpoints are
public (no auth) like ``/ops/status`` and return ONLY counts / aggregates
— never user_id, patient identifiers, or raw health metrics.

Design rules baked into every endpoint here:

- Raw SQL via ``sqlalchemy.text``. No ORM model imports, no pandas, no scipy,
  no ``backend.ml.*`` imports. Keeps the ML boundary clean (see
  ``tests/ml/test_boundary.py``) and keeps cold-boot fast.
- Per-field try/except so a missing table returns ``null`` for that field
  instead of 500-ing the whole response. Staging and dev DBs often lag
  production migrations by a phase or two; every endpoint must degrade
  gracefully.
- NO writes. These are consumed by scheduled tasks that decide whether to
  open Linear issues; they must never mutate state.
"""

from __future__ import annotations

import logging
import statistics
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

logger = logging.getLogger("meld.ops.ml")

router = APIRouter(prefix="/ops/ml", tags=["ops"])


# Raw source tables keyed by source name. Each tuple is (table_name,
# timestamp_column). A missing table is treated as "source not present in
# this environment" and surfaced as null fields, not a 500.
_SOURCE_TABLES: dict[str, tuple[str, str]] = {
    "oura": ("sleep_records", "synced_at"),
    "garmin": ("garmin_daily_records", "synced_at"),
    "peloton": ("workout_records", "synced_at"),
    "apple_health": ("activity_records", "synced_at"),
}


# -- Response models --


class SignalQualityResponse(BaseModel):
    timestamp: str
    l2_counts_by_tier: dict[str, int]
    l3_granger_pairs_count: int | None
    l4_causal_candidates_count: int | None
    ranker_ndcg_p50_last_7d: float | None
    insight_ctr_last_7d: float | None


class DataSourceFreshness(BaseModel):
    last_ingest: str | None
    days_stale: int | None
    row_count_last_30d: int | None


class DataQualityResponse(BaseModel):
    timestamp: str
    sources: dict[str, DataSourceFreshness]
    canonical_freshness_days: int | None


class DriftedFeature(BaseModel):
    feature: str
    ks_stat: float
    threshold: float


class FeatureDriftResponse(BaseModel):
    timestamp: str
    last_computed: str | None
    features_over_threshold: list[DriftedFeature]
    total_features_checked: int
    drifted_count: int


class ActiveExperiment(BaseModel):
    id: int
    name: str
    phase: str
    days_active: int
    users_enrolled: int


class ExperimentsResponse(BaseModel):
    timestamp: str
    active_experiments: list[ActiveExperiment]
    completed_last_30d: int


class RetrainReadinessResponse(BaseModel):
    timestamp: str
    last_training_run: str | None
    days_since_last_training: int | None
    labeled_feedback_since_last_training: int
    ndcg_p50_last_30d: float | None
    recommendation: str  # "retrain" | "wait" | "insufficient_data"


class ModelEntry(BaseModel):
    id: int
    kind: str
    version: str
    created_at: str | None
    active: bool


class ModelRegistryResponse(BaseModel):
    timestamp: str
    models: list[ModelEntry]
    total_count: int
    latest_ranker_version: str | None


# -- Helpers --


def _iso(value: Any) -> str | None:
    """Normalize a DB timestamp to ISO-8601 with a ``T`` separator.

    SQLite returns DateTime values as strings with a space separator; Postgres
    returns ``datetime`` objects. Normalize both so downstream JSON consumers
    never have to branch.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    s = str(value)
    if len(s) >= 11 and s[10] == " ":
        s = s[:10] + "T" + s[11:]
    return s


def _days_between(iso_ts: str | None, now: datetime) -> int | None:
    """Return whole days between an ISO timestamp and ``now``, or None."""
    if not iso_ts:
        return None
    try:
        s = iso_ts.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(s)
        # Strip tz so we can diff against a naive reference if needed.
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        ref = now.replace(tzinfo=None) if now.tzinfo else now
        return max(0, (ref - parsed).days)
    except Exception:
        return None


async def _scalar_or_none(db: AsyncSession, sql: str, **params: Any) -> Any:
    """Run a SELECT and return the first scalar, or None on any failure."""
    try:
        row = await db.execute(text(sql), params)
        return row.scalar()
    except Exception:
        await db.rollback()
        return None


# -- /ops/ml/signal-quality --


async def _l2_counts_by_tier(db: AsyncSession) -> dict[str, int]:
    """Count ``user_correlations`` rows per confidence tier.

    Returns an empty dict when the table does not exist. Tiers with zero rows
    are still returned so the monitor can alert on "ladder broke" conditions
    (e.g. zero established correlations for a week).
    """
    tiers = [
        "emerging",
        "developing",
        "established",
        "literature_supported",
        "causal_candidate",
    ]
    out: dict[str, int] = {t: 0 for t in tiers}
    try:
        result = await db.execute(
            text(
                "SELECT confidence_tier, COUNT(*) "
                "FROM user_correlations "
                "GROUP BY confidence_tier"
            )
        )
        for tier, cnt in result.all():
            if tier in out:
                out[tier] = int(cnt or 0)
    except Exception:
        await db.rollback()
        return {}
    return out


async def _ranker_ndcg_p50(db: AsyncSession, days: int = 7) -> float | None:
    """Median (p50) rank of feedback-positive candidates in the last N days.

    We do not store per-ranking NDCG on the row, so this approximates quality
    with the median rank of the candidate that actually got the thumbs-up
    (lower is better; rank 1 means the ranker put the loved card on top).

    Returns None when there is no feedback data. Pulls into Python and
    computes the median there so we stay dialect-free.
    """
    try:
        since = (
            datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
        ).isoformat()
        result = await db.execute(
            text(
                "SELECT rank FROM ml_rankings "
                "WHERE feedback = 'thumbs_up' "
                "AND created_at >= :since"
            ),
            {"since": since},
        )
        ranks = [int(r[0]) for r in result.all() if r[0] is not None]
    except Exception:
        await db.rollback()
        return None
    if not ranks:
        return None
    return float(statistics.median(ranks))


async def _insight_ctr(db: AsyncSession, days: int = 7) -> float | None:
    """Thumbs-up / shown ratio for insights in the last N days."""
    try:
        since = (
            datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
        ).isoformat()
        shown = await _scalar_or_none(
            db,
            "SELECT COUNT(*) FROM ml_rankings "
            "WHERE was_shown = :t AND created_at >= :since",
            t=True,
            since=since,
        )
        thumbs = await _scalar_or_none(
            db,
            "SELECT COUNT(*) FROM ml_rankings "
            "WHERE was_shown = :t AND feedback = 'thumbs_up' "
            "AND created_at >= :since",
            t=True,
            since=since,
        )
    except Exception:
        await db.rollback()
        return None
    if not shown:
        return None
    try:
        return round(float(thumbs or 0) / float(shown), 4)
    except Exception:
        await db.rollback()
        return None


@router.get("/signal-quality", response_model=SignalQualityResponse)
async def signal_quality(
    db: AsyncSession = Depends(get_db),
) -> SignalQualityResponse:
    """Aggregate L2/L3/L4 signal counts + ranker quality proxies.

    Every sub-query is try/excepted so a missing table (e.g. on a fresh
    dev DB without the discovery migration) degrades to null, not 500.
    """
    l2 = await _l2_counts_by_tier(db)
    l3_count = await _scalar_or_none(
        db, "SELECT COUNT(*) FROM ml_directional_tests WHERE significant = :t", t=True
    )
    l4_count = await _scalar_or_none(
        db,
        "SELECT COUNT(*) FROM ml_causal_estimates "
        "WHERE all_refutations_passed = :t AND ci_excludes_zero = :t",
        t=True,
    )
    ndcg_p50 = await _ranker_ndcg_p50(db, days=7)
    ctr = await _insight_ctr(db, days=7)

    return SignalQualityResponse(
        timestamp=datetime.now(timezone.utc).isoformat(),
        l2_counts_by_tier=l2,
        l3_granger_pairs_count=int(l3_count) if l3_count is not None else None,
        l4_causal_candidates_count=int(l4_count) if l4_count is not None else None,
        ranker_ndcg_p50_last_7d=ndcg_p50,
        insight_ctr_last_7d=ctr,
    )


# -- /ops/ml/data-quality --


async def _source_freshness(
    db: AsyncSession, table: str, col: str, now: datetime
) -> DataSourceFreshness:
    """Return last_ingest / days_stale / row_count_last_30d for one source.

    Any exception (missing table, missing column) collapses to all-null so
    the monitor can distinguish "stale" (old timestamp) from "absent"
    (everything null).
    """
    last: str | None = None
    stale: int | None = None
    count: int | None = None

    # last_ingest
    try:
        val = await _scalar_or_none(db, f"SELECT MAX({col}) FROM {table}")  # noqa: S608
        last = _iso(val)
        stale = _days_between(last, now)
    except Exception:
        await db.rollback()
        pass

    # row_count_last_30d
    try:
        since_iso = (now - timedelta(days=30)).isoformat()
        cnt = await _scalar_or_none(
            db,
            f"SELECT COUNT(*) FROM {table} WHERE {col} >= :since",  # noqa: S608
            since=since_iso,
        )
        if cnt is not None:
            count = int(cnt)
    except Exception:
        await db.rollback()
        pass

    return DataSourceFreshness(
        last_ingest=last, days_stale=stale, row_count_last_30d=count
    )


@router.get("/data-quality", response_model=DataQualityResponse)
async def data_quality(db: AsyncSession = Depends(get_db)) -> DataQualityResponse:
    """Per-source freshness + simple completeness."""
    now = datetime.now(timezone.utc)
    sources: dict[str, DataSourceFreshness] = {}
    for name, (table, col) in _SOURCE_TABLES.items():
        sources[name] = await _source_freshness(db, table, col, now)

    canonical_stale: int | None = None
    try:
        val = await _scalar_or_none(
            db, "SELECT MAX(created_at) FROM health_metric_records"
        )
        canonical_stale = _days_between(_iso(val), now)
    except Exception:
        await db.rollback()
        pass

    return DataQualityResponse(
        timestamp=now.isoformat(),
        sources=sources,
        canonical_freshness_days=canonical_stale,
    )


# -- /ops/ml/feature-drift --


@router.get("/feature-drift", response_model=FeatureDriftResponse)
async def feature_drift(
    db: AsyncSession = Depends(get_db),
) -> FeatureDriftResponse:
    """Return latest synth-vs-real KS drift snapshot.

    Reads the most recent batch from ``ml_drift_results`` (one row per
    ``(synth_run_id, feature_key)`` populated by ``synth_drift_job``).
    The "most recent batch" is the synth_run_id whose MAX(computed_at)
    is the largest across the table. Returns empty arrays when the
    table exists but is empty (freshly migrated, no drift run yet) or
    is missing entirely (staging lags production by a phase).

    All counts / lists, never per-user data.
    """
    now = datetime.now(timezone.utc)
    last_computed: str | None = None
    features: list[DriftedFeature] = []
    total = 0
    drifted_count = 0

    # Identify the most recent batch. One query gets the synth_run_id of
    # the newest row; a second bounds the "as of" timestamp to that run's
    # rows. If the table is missing entirely the first call raises and we
    # fall through to the empty response (graceful staging degradation).
    latest_run_id: Any = None
    try:
        latest_run_id = await _scalar_or_none(
            db,
            "SELECT synth_run_id FROM ml_drift_results "
            "ORDER BY computed_at DESC LIMIT 1",
        )
    except Exception:
        await db.rollback()
        latest_run_id = None

    if latest_run_id is not None:
        try:
            latest_ts = await _scalar_or_none(
                db,
                "SELECT MAX(computed_at) FROM ml_drift_results "
                "WHERE synth_run_id = :run_id",
                run_id=latest_run_id,
            )
            last_computed = _iso(latest_ts)
        except Exception:
            await db.rollback()
            last_computed = None

        try:
            result = await db.execute(
                text(
                    "SELECT feature_key, ks_statistic, threshold, drifted "
                    "FROM ml_drift_results "
                    "WHERE synth_run_id = :run_id "
                    "ORDER BY feature_key"
                ),
                {"run_id": latest_run_id},
            )
            for row in result.all():
                total += 1
                # SQLite returns drifted as 0/1 int; bool() works in both.
                if bool(row[3]):
                    drifted_count += 1
                    features.append(
                        DriftedFeature(
                            feature=str(row[0]),
                            ks_stat=float(row[1]),
                            threshold=float(row[2]),
                        )
                    )
        except Exception:
            await db.rollback()
            features = []
            total = 0
            drifted_count = 0

    return FeatureDriftResponse(
        timestamp=now.isoformat(),
        last_computed=last_computed,
        features_over_threshold=features,
        total_features_checked=total,
        drifted_count=drifted_count,
    )


# -- /ops/ml/experiments --


def _experiment_phase_from_status(status: str | None) -> str:
    """Map internal status to a public phase label.

    The ``ml_experiments.status`` enum uses internal names (``baseline``,
    ``washout_1``, ``treatment``, ``analyzing``). The public phase label
    collapses these into user-facing buckets: ``gathering`` while data is
    still coming in, ``analyzing`` once APTE is running, ``unknown`` as a
    safety default.
    """
    if not status:
        return "unknown"
    if status in ("baseline", "washout_1", "treatment"):
        return "gathering"
    if status == "analyzing":
        return "analyzing"
    return status


@router.get("/experiments", response_model=ExperimentsResponse)
async def experiments(db: AsyncSession = Depends(get_db)) -> ExperimentsResponse:
    """Summary of active + recently-completed APTE experiments.

    Responses never include user_id. ``users_enrolled`` is a distinct-user
    count per experiment row, so even if ``ml_experiments`` ever grew a
    shared-experiment model, this would still collapse to an aggregate.
    """
    now = datetime.now(timezone.utc)
    active: list[ActiveExperiment] = []
    completed_30d = 0

    try:
        result = await db.execute(
            text(
                "SELECT id, experiment_name, status, started_at "
                "FROM ml_experiments "
                "WHERE status IN ('baseline','washout_1','treatment','analyzing') "
                "ORDER BY started_at DESC"
            )
        )
        rows = result.all()
    except Exception:
        await db.rollback()
        rows = []

    for row in rows:
        started_iso = _iso(row[3])
        days_active = _days_between(started_iso, now) or 0
        enrolled = 0
        try:
            cnt = await _scalar_or_none(
                db,
                "SELECT COUNT(DISTINCT user_id) FROM ml_experiments WHERE id = :i",
                i=row[0],
            )
            enrolled = int(cnt or 0)
        except Exception:
            await db.rollback()
            enrolled = 0
        active.append(
            ActiveExperiment(
                id=int(row[0]),
                name=str(row[1] or ""),
                phase=_experiment_phase_from_status(row[2]),
                days_active=days_active,
                users_enrolled=enrolled,
            )
        )

    try:
        since_iso = (now - timedelta(days=30)).isoformat()
        cnt = await _scalar_or_none(
            db,
            "SELECT COUNT(*) FROM ml_experiments "
            "WHERE status = 'completed' AND completed_at >= :since",
            since=since_iso,
        )
        completed_30d = int(cnt or 0)
    except Exception:
        await db.rollback()
        completed_30d = 0

    return ExperimentsResponse(
        timestamp=now.isoformat(),
        active_experiments=active,
        completed_last_30d=completed_30d,
    )


# -- /ops/ml/retrain-readiness --


@router.get("/retrain-readiness", response_model=RetrainReadinessResponse)
async def retrain_readiness(
    db: AsyncSession = Depends(get_db),
) -> RetrainReadinessResponse:
    """Decision support for the weekly retrain scheduler.

    Recommendation logic lives in this endpoint so the scheduler does not
    need its own copy of the thresholds:

    - ``insufficient_data`` if < 20 labeled feedback rows since last train
    - ``retrain`` if >= 20 labeled AND >= 14 days since last train
    - ``wait`` otherwise
    """
    now = datetime.now(timezone.utc)
    last_iso: str | None = None
    try:
        val = await _scalar_or_none(
            db,
            "SELECT MAX(finished_at) FROM ml_training_runs WHERE status = 'completed'",
        )
        last_iso = _iso(val)
    except Exception:
        await db.rollback()
        last_iso = None

    days_since = _days_between(last_iso, now)

    labeled = 0
    try:
        if last_iso:
            cnt = await _scalar_or_none(
                db,
                "SELECT COUNT(*) FROM ml_rankings "
                "WHERE feedback IS NOT NULL AND created_at > :since",
                since=last_iso,
            )
        else:
            cnt = await _scalar_or_none(
                db,
                "SELECT COUNT(*) FROM ml_rankings WHERE feedback IS NOT NULL",
            )
        labeled = int(cnt or 0)
    except Exception:
        await db.rollback()
        labeled = 0

    ndcg_30 = await _ranker_ndcg_p50(db, days=30)

    if labeled < 20:
        rec = "insufficient_data"
    elif days_since is not None and days_since >= 14:
        rec = "retrain"
    else:
        rec = "wait"

    return RetrainReadinessResponse(
        timestamp=now.isoformat(),
        last_training_run=last_iso,
        days_since_last_training=days_since,
        labeled_feedback_since_last_training=labeled,
        ndcg_p50_last_30d=ndcg_30,
        recommendation=rec,
    )


# -- /ops/ml/model-registry --


@router.get("/model-registry", response_model=ModelRegistryResponse)
async def model_registry(
    db: AsyncSession = Depends(get_db),
) -> ModelRegistryResponse:
    """MLflow-free snapshot of the ``ml_models`` registry.

    Returns up to 50 most recent rows; the total_count is reported
    separately so scheduled tasks can detect table growth without having
    to fetch every row.
    """
    now = datetime.now(timezone.utc)
    models: list[ModelEntry] = []
    total = 0
    latest_ranker: str | None = None

    try:
        result = await db.execute(
            text(
                "SELECT id, model_type, model_version, created_at, is_active "
                "FROM ml_models "
                "ORDER BY created_at DESC "
                "LIMIT 50"
            )
        )
        for row in result.all():
            models.append(
                ModelEntry(
                    id=int(row[0]),
                    kind=str(row[1] or ""),
                    version=str(row[2] or ""),
                    created_at=_iso(row[3]),
                    active=bool(row[4]),
                )
            )
    except Exception:
        await db.rollback()
        models = []

    try:
        cnt = await _scalar_or_none(db, "SELECT COUNT(*) FROM ml_models")
        total = int(cnt or 0)
    except Exception:
        await db.rollback()
        total = 0

    try:
        val = await _scalar_or_none(
            db,
            "SELECT model_version FROM ml_models "
            "WHERE model_type = 'ranker' AND is_active = :t "
            "ORDER BY created_at DESC LIMIT 1",
            t=True,
        )
        if val is not None:
            latest_ranker = str(val)
        else:
            # Fall back to the most recent ranker even if not active.
            val2 = await _scalar_or_none(
                db,
                "SELECT model_version FROM ml_models "
                "WHERE model_type = 'ranker' "
                "ORDER BY created_at DESC LIMIT 1",
            )
            latest_ranker = str(val2) if val2 is not None else None
    except Exception:
        await db.rollback()
        latest_ranker = None

    return ModelRegistryResponse(
        timestamp=now.isoformat(),
        models=models,
        total_count=total,
        latest_ranker_version=latest_ranker,
    )
