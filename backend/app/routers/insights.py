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

from app.api.deps import CurrentUser
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


@router.post("/{ranking_id}/feedback", status_code=204)
async def post_insight_feedback(
    ranking_id: int,
    req: FeedbackRequest,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Record user feedback on a surfaced insight. 204 No Content on success.

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
