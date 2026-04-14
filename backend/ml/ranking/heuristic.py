"""Heuristic ranker for Phase 4.

Fixed weighted-sum scorer over the normalized candidate fields. The learned
XGBoost LambdaMART ranker arrives in Phase 7. Keeping the math here very
simple and the weights in one place makes it trivial to A/B the heuristic
against the learned ranker once we have enough labeled pairs.

Weights match the plan spec:

    score = 0.35 * effect_size
          + 0.25 * confidence
          + 0.15 * actionability_score
          + 0.15 * novelty
          + 0.10 * (literature_support ? 1 : 0)

All inputs are already 0-1 normalized (see ``candidates.py``), so the
output is also 0-1. Strong correlations with literature backing on
modifiable behaviors top out near 1.0.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import and_, select

from ml.ranking.candidates import InsightCandidate, RANKER_VERSION

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# Plan-specified weights. Any tweak should update the docstring above and
# the comment in the plan file, and bump RANKER_VERSION.
_W_EFFECT = 0.35
_W_CONFIDENCE = 0.25
_W_ACTIONABILITY = 0.15
_W_NOVELTY = 0.15
_W_LITERATURE = 0.10

# Hard exposure caps per the plan (``MLSettings.ranker_max_candidates_*``).
# Enforced in ``materialize_daily_ranking`` rather than in the scorer so
# scoring stays pure and testable.
MAX_CARDS_PER_DAY = 1
MAX_CARDS_PER_WEEK = 3


@dataclass
class RankedCandidate:
    """A candidate with its score + rank within one user-day slate."""

    candidate: InsightCandidate
    score: float
    rank: int


def heuristic_score(candidate: InsightCandidate) -> float:
    """Weighted sum. Returns a value in [0, 1].

    Pure function; easy to unit-test against known inputs.
    """
    return (
        _W_EFFECT * candidate.effect_size
        + _W_CONFIDENCE * candidate.confidence
        + _W_ACTIONABILITY * candidate.actionability_score
        + _W_NOVELTY * candidate.novelty
        + _W_LITERATURE * (1.0 if candidate.literature_support else 0.0)
    )


def rank_candidates(candidates: list[InsightCandidate]) -> list[RankedCandidate]:
    """Score + sort. Stable tiebreak by candidate id for reproducibility."""
    scored = [(heuristic_score(c), c) for c in candidates]
    scored.sort(key=lambda pair: (-pair[0], pair[1].id))
    return [
        RankedCandidate(candidate=c, score=round(s, 6), rank=i + 1)
        for i, (s, c) in enumerate(scored)
    ]


# ─────────────────────────────────────────────────────────────────────────
# Cap enforcement + persistence
# ─────────────────────────────────────────────────────────────────────────


async def _shown_count_in_window(
    db: "AsyncSession",
    user_id: str,
    window_start_date: date,
    window_end_date: date,
) -> int:
    """How many rank=1 cards were shown to this user in the window."""
    from app.models.ml_insights import MLRanking

    result = await db.execute(
        select(MLRanking).where(
            MLRanking.user_id == user_id,
            MLRanking.was_shown.is_(True),
            MLRanking.rank == 1,
            MLRanking.surface_date >= window_start_date.isoformat(),
            MLRanking.surface_date <= window_end_date.isoformat(),
        )
    )
    return len(list(result.scalars().all()))


async def _existing_ranking_for_day(
    db: "AsyncSession",
    user_id: str,
    surface_date: date,
    ranker_version: str,
) -> bool:
    """True if we have already persisted a ranking slate for this (user, date, ranker).

    Lets the scheduler rerun the job without creating duplicate slates.
    """
    from app.models.ml_insights import MLRanking

    result = await db.execute(
        select(MLRanking).where(
            and_(
                MLRanking.user_id == user_id,
                MLRanking.surface_date == surface_date.isoformat(),
                MLRanking.ranker_version == ranker_version,
            )
        )
    )
    return result.first() is not None


async def materialize_daily_ranking(
    db: "AsyncSession",
    user_id: str,
    candidates: list[InsightCandidate],
    surface_date: date,
    keep_top_n: int = 5,
) -> list[RankedCandidate]:
    """Rank + persist the daily slate, respecting exposure caps.

    - Already surfaced today / under cap? No-op (idempotent rerun).
    - Over weekly cap (3 in trailing 7 days)? Log + write rankings with
      ``was_shown=False`` anyway so the shadow log captures what WOULD
      have been shown. The API layer enforces ``was_shown`` before
      sending to iOS.
    - Writes top ``keep_top_n`` rankings; only rank 1 will ever be shown.
      Rank 2+ is kept for A/B / Phase 7 ranker training data.

    Returns the list of RankedCandidate rows written.
    """
    from app.core.time import utcnow_naive
    from app.models.ml_insights import MLRanking

    # Idempotent: if the slate already exists for this (user, date, ranker),
    # return empty (the scheduler is calling us a second time today).
    if await _existing_ranking_for_day(db, user_id, surface_date, RANKER_VERSION):
        return []

    if not candidates:
        return []

    ranked = rank_candidates(candidates)[:keep_top_n]
    now = utcnow_naive()
    for r in ranked:
        db.add(
            MLRanking(
                user_id=user_id,
                surface_date=surface_date.isoformat(),
                candidate_id=r.candidate.id,
                rank=r.rank,
                score=r.score,
                ranker_version=RANKER_VERSION,
                was_shown=False,  # flipped when iOS actually renders
                created_at=now,
            )
        )
    await db.flush()
    return ranked


async def can_surface_today(
    db: "AsyncSession", user_id: str, surface_date: date
) -> tuple[bool, str]:
    """Cap check: True = OK to show the top-1 card to the user today.

    Returns (allowed, reason) so callers can log why a day was skipped.
    """
    # Daily cap: only one rank=1 card per day may be shown.
    today_shown = await _shown_count_in_window(db, user_id, surface_date, surface_date)
    if today_shown >= MAX_CARDS_PER_DAY:
        return False, f"daily cap hit ({today_shown}/{MAX_CARDS_PER_DAY})"

    # Weekly cap: 3 in the trailing 7 days (inclusive of today).
    week_start = surface_date - timedelta(days=6)
    week_shown = await _shown_count_in_window(db, user_id, week_start, surface_date)
    if week_shown >= MAX_CARDS_PER_WEEK:
        return False, f"weekly cap hit ({week_shown}/{MAX_CARDS_PER_WEEK})"

    return True, "ok"
