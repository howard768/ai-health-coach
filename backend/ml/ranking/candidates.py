"""Phase 4 candidate normalization.

Reads the downstream ML output tables (``UserCorrelation``, ``ml_anomalies``,
``ml_forecasts``) and normalizes each surfaceable finding into a common
``InsightCandidate`` shape that the ranker can score apples-to-apples.

Candidate IDs are deterministic hashes of (user, kind, canonical subject)
so rerunning generation on the same day produces the same row ids and
``ml_rankings`` can reference them stably.

Heavy imports (pandas, numpy) stay lazy per the cold-boot budget.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


RANKER_VERSION = "heuristic-1.0.0"


# Modifiable-behavior feature keys get higher actionability. These are
# things the user can realistically change in the next 24-72 hours.
# Biometric-only findings (hrv, resting_hr, readiness_score, sleep_efficiency
# without a behavioral cause) score lower because "change your HRV" is not
# a direct action.
_HIGH_ACTIONABILITY_KEYS: set[str] = {
    "steps",
    "active_calories",
    "workout_count",
    "workout_duration_sum_minutes",
    "training_load_7d",
    "protein_g",
    "calories",
    "carbs_g",
    "fat_g",
    "meal_count",
    "dinner_hour",  # future feature
    # Legacy names that may appear in UserCorrelation.source_metric:
    "protein_intake",
    "total_calories",
    "workout_duration",
}

# Confidence tier -> [0, 1].
_TIER_CONFIDENCE: dict[str, float] = {
    "emerging": 0.30,
    "developing": 0.60,
    "established": 0.80,
    "causal_candidate": 0.90,
    "literature_supported": 0.95,
}


@dataclass
class InsightCandidate:
    """Normalized shape for the ranker.

    This is the in-memory representation; the persisted shape lives in
    ``ml_insight_candidates`` (see ``app/models/ml_insights.py``).
    """

    id: str
    user_id: str
    kind: str  # correlation | anomaly | forecast_warning | experiment_result | streak | regression
    subject_metrics: tuple[str, ...]
    effect_size: float  # 0-1
    confidence: float  # 0-1
    novelty: float  # 0-1
    recency_days: int
    actionability_score: float  # 0-1
    literature_support: bool = False
    directional_support: bool = False
    causal_support: bool = False
    payload: dict[str, Any] = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────
# ID hashing
# ─────────────────────────────────────────────────────────────────────────


def make_candidate_id(user_id: str, kind: str, *subject_parts: str) -> str:
    """SHA-1 hex of a canonical tuple, truncated to 24 chars.

    Deterministic per (user, kind, subject) so reruns on the same day land
    on the same row. 24 hex chars = 96 bits, enough to avoid collisions at
    our scale while keeping the DB column small.
    """
    payload = "|".join([user_id, kind, *subject_parts])
    # SHA-1 chosen for compact deterministic ID (non-cryptographic).
    # usedforsecurity=False tells hashlib it's a checksum; Semgrep's rule
    # doesn't recognize the arg so we suppress here.
    # nosemgrep: python.lang.security.insecure-hash-algorithms.insecure-hash-algorithm-sha1
    return hashlib.sha1(payload.encode("utf-8"), usedforsecurity=False).hexdigest()[:24]


# ─────────────────────────────────────────────────────────────────────────
# Per-kind builders
# ─────────────────────────────────────────────────────────────────────────


async def _build_correlation_candidates(
    db: "AsyncSession", user_id: str, through_date: date
) -> list[InsightCandidate]:
    """UserCorrelation rows at developing+ tier become correlation candidates."""
    from app.models.correlation import UserCorrelation

    result = await db.execute(
        select(UserCorrelation).where(
            UserCorrelation.user_id == user_id,
            UserCorrelation.confidence_tier.in_(
                ("developing", "established", "causal_candidate", "literature_supported")
            ),
        )
    )
    rows = list(result.scalars().all())

    candidates: list[InsightCandidate] = []
    for row in rows:
        effect = min(abs(row.strength or 0.0), 1.0)
        tier = row.confidence_tier or "emerging"
        confidence = _TIER_CONFIDENCE.get(tier, 0.30)

        actionability = (
            1.0 if row.source_metric in _HIGH_ACTIONABILITY_KEYS else 0.5
        )

        recency_base = row.last_validated_at or row.discovered_at
        recency_days = 0
        if recency_base is not None:
            recency_days = max(0, (through_date - recency_base.date()).days)

        candidate_id = make_candidate_id(
            user_id,
            "correlation",
            row.source_metric,
            row.target_metric,
            str(row.lag_days or 0),
        )

        candidates.append(
            InsightCandidate(
                id=candidate_id,
                user_id=user_id,
                kind="correlation",
                subject_metrics=(row.source_metric, row.target_metric),
                effect_size=effect,
                confidence=confidence,
                novelty=0.0,  # filled in later
                recency_days=recency_days,
                actionability_score=actionability,
                literature_support=bool(row.literature_match),
                directional_support=False,  # set true in Phase 6 when L3 Granger populates
                causal_support=(tier == "causal_candidate"),
                payload={
                    "source_metric": row.source_metric,
                    "target_metric": row.target_metric,
                    "lag_days": row.lag_days,
                    "direction": row.direction,
                    "pearson_r": row.pearson_r,
                    "spearman_r": row.spearman_r,
                    "sample_size": row.sample_size,
                    "fdr_adjusted_p": row.fdr_adjusted_p,
                    "effect_description": row.effect_size_description,
                    "confidence_tier": tier,
                    "literature_ref": row.literature_ref,
                },
            )
        )
    return candidates


async def _build_anomaly_candidates(
    db: "AsyncSession", user_id: str, through_date: date, lookback_days: int = 7
) -> list[InsightCandidate]:
    """Recent ml_anomalies rows become anomaly candidates.

    Confirmed-by-BOCPD anomalies get a directional_support flag (the change
    point registered independently, two-signal confirmation). Uncorroborated
    z-score spikes still surface but score lower via confidence.
    """
    from app.models.ml_baselines import MLAnomaly

    start = (through_date - timedelta(days=lookback_days - 1)).isoformat()

    result = await db.execute(
        select(MLAnomaly).where(
            MLAnomaly.user_id == user_id,
            MLAnomaly.observation_date >= start,
            MLAnomaly.observation_date <= through_date.isoformat(),
        )
    )
    rows = list(result.scalars().all())

    candidates: list[InsightCandidate] = []
    for row in rows:
        effect = min(abs(row.z_score) / 5.0, 1.0)
        # Base confidence by BOCPD confirmation.
        confidence = 0.80 if row.confirmed_by_bocpd else 0.60

        recency_days = max(
            0, (through_date - date.fromisoformat(row.observation_date)).days
        )
        # Biometrics are harder to act on than behaviors; low actionability.
        actionability = 0.4

        candidate_id = make_candidate_id(
            user_id,
            "anomaly",
            row.metric_key,
            row.observation_date,
        )

        candidates.append(
            InsightCandidate(
                id=candidate_id,
                user_id=user_id,
                kind="anomaly",
                subject_metrics=(row.metric_key,),
                effect_size=effect,
                confidence=confidence,
                novelty=0.0,
                recency_days=recency_days,
                actionability_score=actionability,
                literature_support=False,
                directional_support=bool(row.confirmed_by_bocpd),
                causal_support=False,
                payload={
                    "metric_key": row.metric_key,
                    "observation_date": row.observation_date,
                    "observed_value": row.observed_value,
                    "forecasted_value": row.forecasted_value,
                    "residual": row.residual,
                    "z_score": row.z_score,
                    "direction": row.direction,
                    "confirmed_by_bocpd": row.confirmed_by_bocpd,
                },
            )
        )
    return candidates


# ─────────────────────────────────────────────────────────────────────────
# Novelty scoring
# ─────────────────────────────────────────────────────────────────────────


async def _compute_novelty_scores(
    db: "AsyncSession",
    user_id: str,
    candidates: list[InsightCandidate],
    through_date: date,
    history_days: int = 30,
) -> None:
    """Populate ``novelty`` in place.

    Simple rule (matches the plan's spec of ``1 - cosine_sim to last 30d
    surfaced``): if the same (kind, canonical subject) has been shown to
    the user in the last ``history_days``, novelty = 0.4. Otherwise 1.0.
    A ranker-visible nudge against repeats, without needing a full vector
    embedding in Phase 4.
    """
    from app.models.ml_insights import MLRanking

    start = (through_date - timedelta(days=history_days - 1)).isoformat()

    recent = await db.execute(
        select(MLRanking.candidate_id).where(
            MLRanking.user_id == user_id,
            MLRanking.was_shown.is_(True),
            MLRanking.surface_date >= start,
            MLRanking.surface_date <= through_date.isoformat(),
        )
    )
    shown_ids = {r for r in recent.scalars().all()}

    for cand in candidates:
        cand.novelty = 0.4 if cand.id in shown_ids else 1.0


# ─────────────────────────────────────────────────────────────────────────
# Public entry
# ─────────────────────────────────────────────────────────────────────────


async def generate_candidates(
    db: "AsyncSession", user_id: str, through_date: date
) -> list[InsightCandidate]:
    """Build every surfaceable candidate for a user on a given day.

    Persists to ``ml_insight_candidates`` (idempotent upsert). Does NOT
    commit — caller owns the transaction. Returns the in-memory list so
    the ranker can use it without re-reading.
    """
    from app.core.time import utcnow_naive
    from app.models.ml_insights import MLInsightCandidate

    candidates: list[InsightCandidate] = []
    candidates.extend(await _build_correlation_candidates(db, user_id, through_date))
    candidates.extend(await _build_anomaly_candidates(db, user_id, through_date))

    await _compute_novelty_scores(db, user_id, candidates, through_date)

    # Nothing to upsert? Skip the query entirely so SQLAlchemy does not
    # have to evaluate ``.in_([])`` (which is valid but wasteful).
    if not candidates:
        return candidates

    # Upsert each into ml_insight_candidates. Candidate ids are deterministic
    # so we can "merge by id" rather than delete + insert.
    now = utcnow_naive()
    existing = await db.execute(
        select(MLInsightCandidate.id).where(
            MLInsightCandidate.id.in_([c.id for c in candidates])
        )
    )
    existing_ids = {r for r in existing.scalars().all()}

    for cand in candidates:
        subject_json = json.dumps(list(cand.subject_metrics))
        payload_json = json.dumps(cand.payload, default=_json_default) if cand.payload else None
        if cand.id in existing_ids:
            row = await db.get(MLInsightCandidate, cand.id)
            if row is None:
                continue
            row.kind = cand.kind
            row.subject_metrics_json = subject_json
            row.effect_size = cand.effect_size
            row.confidence = cand.confidence
            row.novelty = cand.novelty
            row.recency_days = cand.recency_days
            row.actionability_score = cand.actionability_score
            row.literature_support = cand.literature_support
            row.directional_support = cand.directional_support
            row.causal_support = cand.causal_support
            row.payload_json = payload_json
            row.generated_at = now
        else:
            db.add(
                MLInsightCandidate(
                    id=cand.id,
                    user_id=cand.user_id,
                    kind=cand.kind,
                    subject_metrics_json=subject_json,
                    effect_size=cand.effect_size,
                    confidence=cand.confidence,
                    novelty=cand.novelty,
                    recency_days=cand.recency_days,
                    actionability_score=cand.actionability_score,
                    literature_support=cand.literature_support,
                    directional_support=cand.directional_support,
                    causal_support=cand.causal_support,
                    payload_json=payload_json,
                    generated_at=now,
                )
            )

    await db.flush()
    return candidates


def _json_default(obj: Any) -> Any:
    """JSON serializer for datetime / date / anything the dataclass may carry."""
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    return str(obj)
