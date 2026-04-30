"""Phase 4 Signal Engine insights API.

Exposes the daily ranked insight to iOS and closes the feedback loop.

- ``GET /api/insights/daily`` returns today's top-1 ranking (or an empty
  response when the shadow flag is on, when no candidates were generated,
  or when the exposure cap is hit). Flips ``was_shown`` on the ranking
  row atomically so the cap logic sees it.
- ``POST /api/insights/{ranking_id}/feedback`` records thumbs_up,
  thumbs_down, dismissed, or already_knew. Feeds Phase 7 ranker training.

Shadow-mode gate: ``MLSettings.ml_shadow_insight_card`` defaults to True,
so this endpoint effectively returns nothing until an operator flips the
env flag. The ranker still runs nightly and fills ``ml_rankings`` with
``was_shown=False`` so the shadow log captures what WOULD have shown.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentAdminUser, CurrentUser
from app.core.time import utcnow_naive
from app.database import get_db


logger = logging.getLogger("meld.insights")

router = APIRouter(prefix="/api/insights", tags=["insights"])


# Valid feedback tokens. Stored as a plain column so Phase 7 can extend.
_VALID_FEEDBACK: set[str] = {"thumbs_up", "thumbs_down", "dismissed", "already_knew"}


class DailyInsightCard(BaseModel):
    """Shape returned to iOS for rendering the SignalInsightCard."""

    ranking_id: int
    candidate_id: str
    kind: str
    subject_metrics: list[str]
    effect_size: float
    confidence: float
    score: float
    ranker_version: str
    literature_support: bool
    payload: dict


class DailyInsightResponse(BaseModel):
    """``has_card=False`` when the surface is off (shadow mode, no candidates,
    or cap hit). iOS falls back to the legacy CoachInsightCard in that case."""

    has_card: bool
    card: DailyInsightCard | None = None
    reason: str | None = None  # why has_card=False


class FeedbackRequest(BaseModel):
    feedback: Literal["thumbs_up", "thumbs_down", "dismissed", "already_knew"]


@router.get("/daily", response_model=DailyInsightResponse)
async def get_daily_insight(
    request: Request,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> DailyInsightResponse:
    """Return the top-1 ranked insight for today, if any.

    Also flips ``was_shown=True`` on the ranking row so the cap logic and
    feedback attribution see it. This is a GET by convention (iOS polls it
    from the dashboard); the side-effect is small and idempotent across
    the same day.
    """
    from ml import api as ml_api

    # Lazy-import ORM models to keep cold boot clean.
    from app.models.ml_insights import MLInsightCandidate, MLRanking

    if ml_api.is_insight_card_shadow_mode():
        return DailyInsightResponse(
            has_card=False, reason="shadow_mode"
        )

    today = date.today()
    allowed, reason = await ml_api.can_surface_insight_today(
        db, user.apple_user_id, today
    )
    if not allowed:
        return DailyInsightResponse(has_card=False, reason=reason)

    # Find today's rank=1 that has NOT yet been shown.
    result = await db.execute(
        select(MLRanking).where(
            MLRanking.user_id == user.apple_user_id,
            MLRanking.surface_date == today.isoformat(),
            MLRanking.rank == 1,
        )
    )
    ranking = result.scalar_one_or_none()
    if ranking is None:
        return DailyInsightResponse(has_card=False, reason="no_candidate_today")

    # Look up the candidate payload.
    candidate = await db.get(MLInsightCandidate, ranking.candidate_id)
    if candidate is None:
        logger.warning(
            "ranking %s points at missing candidate %s",
            ranking.id,
            ranking.candidate_id,
        )
        return DailyInsightResponse(has_card=False, reason="candidate_missing")

    # Flip was_shown on first read of the day.
    if not ranking.was_shown:
        ranking.was_shown = True
        ranking.shown_at = utcnow_naive()
        await db.commit()

    subject_metrics = json.loads(candidate.subject_metrics_json)
    payload = json.loads(candidate.payload_json) if candidate.payload_json else {}

    card = DailyInsightCard(
        ranking_id=ranking.id,
        candidate_id=candidate.id,
        kind=candidate.kind,
        subject_metrics=subject_metrics,
        effect_size=candidate.effect_size,
        confidence=candidate.confidence,
        score=ranking.score,
        ranker_version=ranking.ranker_version,
        literature_support=candidate.literature_support,
        payload=payload,
    )
    return DailyInsightResponse(has_card=True, card=card)


class FeedbackAck(BaseModel):
    ok: bool = True


@router.post("/{ranking_id}/feedback", response_model=FeedbackAck)
async def post_insight_feedback(
    ranking_id: int,
    req: FeedbackRequest,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> FeedbackAck:
    """Record user feedback on a surfaced insight.

    Returns 200 ``{"ok": true}`` so the iOS client's generic ``send()``
    helper (which expects 200) can call it without a special variant.

    Rejects feedback on rankings that don't belong to the caller to prevent
    one user writing to another's ranking row. Idempotent re-submissions
    are allowed (update in place) — the user can change their mind.
    """
    from app.models.ml_insights import MLRanking

    if req.feedback not in _VALID_FEEDBACK:
        raise HTTPException(status_code=400, detail="invalid feedback value")

    ranking = await db.get(MLRanking, ranking_id)
    if ranking is None:
        raise HTTPException(status_code=404, detail="ranking not found")
    if ranking.user_id != user.apple_user_id:
        raise HTTPException(status_code=403, detail="not your ranking")

    ranking.feedback = req.feedback
    ranking.feedback_at = utcnow_naive()
    await db.commit()
    return FeedbackAck()


# ─────────────────────────────────────────────────────────────────────────
# Phase 7B: candidates endpoint + ranker metadata
# ─────────────────────────────────────────────────────────────────────────


class CandidateFeaturesOut(BaseModel):
    """Feature vector for one candidate, used by iOS on-device ranking."""

    candidate_id: str
    kind: str
    subject_metrics: list[str]
    effect_size: float
    confidence: float
    novelty: float
    recency_days: int
    actionability_score: float
    literature_support: bool
    directional_support: bool
    causal_support: bool
    payload: dict


class CandidatesResponse(BaseModel):
    """All of today's candidates for on-device ranking."""

    candidates: list[CandidateFeaturesOut]


class RankerMetadataResponse(BaseModel):
    """CoreML model metadata for conditional download."""

    model_version: str
    file_hash: str
    file_size_bytes: int
    download_url: str


@router.get("/candidates", response_model=CandidatesResponse)
async def get_candidates(
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> CandidatesResponse:
    """Return today's unranked candidate pool with feature vectors.

    Used by iOS for on-device CoreML ranking (Phase 7B). Returns all
    candidates that were generated for today, regardless of shadow mode
    or cap status. The iOS client applies its own ranking.
    """
    from app.models.ml_insights import MLInsightCandidate

    today = date.today()

    result = await db.execute(
        select(MLInsightCandidate).where(
            MLInsightCandidate.user_id == user.apple_user_id,
            MLInsightCandidate.generated_at >= today.isoformat(),
        )
    )
    candidates = result.scalars().all()

    out = []
    for c in candidates:
        subject_metrics = json.loads(c.subject_metrics_json)
        payload = json.loads(c.payload_json) if c.payload_json else {}
        out.append(
            CandidateFeaturesOut(
                candidate_id=c.id,
                kind=c.kind,
                subject_metrics=subject_metrics,
                effect_size=c.effect_size,
                confidence=c.confidence,
                novelty=c.novelty,
                recency_days=c.recency_days,
                actionability_score=c.actionability_score,
                literature_support=c.literature_support,
                directional_support=c.directional_support,
                causal_support=c.causal_support,
                payload=payload,
            )
        )
    return CandidatesResponse(candidates=out)


@router.get("/ranker-metadata", response_model=RankerMetadataResponse)
async def get_ranker_metadata(
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> RankerMetadataResponse:
    """Return the latest active CoreML ranker model metadata.

    iOS uses this to check whether it needs to download a new model.
    The file_hash field enables conditional download (ETag-like).
    Returns 404 when no active model exists.
    """
    from ml import api as ml_api

    metadata = await ml_api.ranker_model_metadata(db)
    if metadata is None:
        raise HTTPException(status_code=404, detail="no active ranker model")

    return RankerMetadataResponse(
        model_version=metadata.model_version,
        file_hash=metadata.file_hash,
        file_size_bytes=metadata.file_size_bytes,
        download_url=metadata.download_url,
    )


# ─────────────────────────────────────────────────────────────────────────
# Phase 10: model rollback
# ─────────────────────────────────────────────────────────────────────────


class RollbackRequest(BaseModel):
    model_type: str
    to_version: str


class RollbackResponse(BaseModel):
    ok: bool
    activated_version: str
    message: str


@router.post("/admin/rollback", response_model=RollbackResponse)
async def rollback_model(
    req: RollbackRequest,
    user: CurrentAdminUser,
    db: AsyncSession = Depends(get_db),
) -> RollbackResponse:
    """Roll back a model to a previous version.

    Deactivates the current active model of the given type and
    re-activates the specified version. Sends alerts to Discord + Telegram.
    """
    from sqlalchemy import select, update

    from app.models.ml_models import MLModel
    from ml import api as ml_api

    # Find the target model.
    result = await db.execute(
        select(MLModel).where(
            MLModel.model_type == req.model_type,
            MLModel.model_version == req.to_version,
        )
    )
    target = result.scalar_one_or_none()
    if target is None:
        raise HTTPException(
            status_code=404,
            detail=f"Model {req.model_type}/{req.to_version} not found",
        )

    # Find current active model for logging.
    current_result = await db.execute(
        select(MLModel).where(
            MLModel.model_type == req.model_type,
            MLModel.is_active.is_(True),
        )
    )
    current = current_result.scalar_one_or_none()
    from_version = current.model_version if current else "none"

    # Deactivate all models of this type.
    await db.execute(
        update(MLModel)
        .where(MLModel.model_type == req.model_type, MLModel.is_active.is_(True))
        .values(is_active=False)
    )

    # Activate the target.
    target.is_active = True
    target.rolled_back_at = utcnow_naive()
    await db.commit()

    # Alert (best-effort) — capture to Sentry so a recurring alert outage
    # doesn't go unnoticed even though the rollback itself succeeds.
    try:
        await ml_api.send_rollback_alert(req.model_type, from_version, req.to_version)
    except Exception as e:  # noqa: BLE001 -- alert failure must not abort rollback
        logger.error("Rollback alert failed: %s", e)
        try:
            import sentry_sdk
            with sentry_sdk.push_scope() as scope:
                scope.set_tag("ml_action", "rollback_alert")
                scope.set_tag("model_type", req.model_type)
                sentry_sdk.capture_exception(e)
        except Exception:  # noqa: BLE001 -- never let Sentry crash the rollback
            logger.debug("Sentry capture failed (non-fatal)", exc_info=True)

    return RollbackResponse(
        ok=True,
        activated_version=req.to_version,
        message=f"Rolled back {req.model_type} from {from_version} to {req.to_version}.",
    )
