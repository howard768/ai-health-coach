"""Mascot customization endpoints.

Tracks which accessories each user has unlocked + which they have equipped
on the home-screen mascot. Backs the iOS `MascotAccessory` enum.

Routes:
  GET   /api/user/mascot          — current state (unlocked + equipped)
  PATCH /api/user/mascot          — equip/unequip an already-unlocked accessory
  POST  /api/user/mascot/unlock   — unlock an accessory for the current user
                                    (idempotent — re-calling is a no-op)

The catalog of accessory IDs lives in the iOS `MascotAccessory` enum, NOT
in the backend. The backend treats accessory_id as opaque. This means
adding a new accessory in iOS doesn't require a backend deploy.

NOTE on /unlock: today this is called directly from the iOS wardrobe screen
as a manual unlock (debug + early-access path). When the achievement
detection system ships, the same endpoint will be called from a
server-side cron / event handler instead of from the client. The shape
stays the same; the trigger source moves.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.time import utcnow_naive
from app.database import get_db
from app.models.mascot import UserMascotState

logger = logging.getLogger("meld.mascot")

router = APIRouter(prefix="/api/user/mascot", tags=["mascot"])


# ── Schemas ──────────────────────────────────────────────────────────────


class MascotStateResponse(BaseModel):
    """Snapshot of the user's mascot wardrobe.

    `equipped` and `unlocked` are both lists of accessory_id strings.
    `unlocked` is the superset (everything the user owns); `equipped` is
    the subset currently shown on the home-screen mascot.
    """

    unlocked: list[str] = Field(default_factory=list)
    equipped: list[str] = Field(default_factory=list)


class EquipRequest(BaseModel):
    accessory_id: str = Field(..., min_length=1, max_length=64)
    equipped: bool


class UnlockRequest(BaseModel):
    """Manual unlock body. Used by the wardrobe debug toggle today; will
    be replaced by server-side achievement detectors later."""

    accessory_id: str = Field(..., min_length=1, max_length=64)


class UnlockResponse(BaseModel):
    """Result of an unlock call. `newly_unlocked` is True the FIRST time
    the user unlocks this accessory; False on idempotent re-unlocks. The
    iOS client uses this to decide whether to show the celebration UI."""

    newly_unlocked: bool
    state: MascotStateResponse


# ── Helpers ──────────────────────────────────────────────────────────────


async def _load_state(db: AsyncSession, user_id: str) -> MascotStateResponse:
    """Read the user's full mascot state into a response model."""
    result = await db.execute(
        select(UserMascotState).where(UserMascotState.user_id == user_id)
    )
    rows = result.scalars().all()
    return MascotStateResponse(
        unlocked=[r.accessory_id for r in rows],
        equipped=[r.accessory_id for r in rows if r.equipped],
    )


# ── Routes ───────────────────────────────────────────────────────────────


@router.get("", response_model=MascotStateResponse)
async def get_mascot_state(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> MascotStateResponse:
    """Return the current user's unlocked + equipped accessories."""
    return await _load_state(db, current_user.apple_user_id)


@router.patch("", response_model=MascotStateResponse)
async def update_mascot_equip(
    body: EquipRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> MascotStateResponse:
    """Equip or unequip an accessory the user has already unlocked.

    Errors:
      404 — accessory not unlocked for this user (can't equip what you
            don't own)
    """
    user_id = current_user.apple_user_id

    result = await db.execute(
        select(UserMascotState).where(
            UserMascotState.user_id == user_id,
            UserMascotState.accessory_id == body.accessory_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Accessory '{body.accessory_id}' is not unlocked for this user",
        )

    row.equipped = body.equipped
    await db.commit()

    return await _load_state(db, user_id)


@router.post("/unlock", response_model=UnlockResponse)
async def unlock_accessory(
    body: UnlockRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> UnlockResponse:
    """Unlock an accessory for the current user. Idempotent.

    First call: creates a UserMascotState row with equipped=False and
    returns `newly_unlocked=True` so the client can show the celebration.

    Subsequent calls with the same accessory_id: no-op, returns
    `newly_unlocked=False`. Safe to call from the wardrobe whenever.

    Note: this endpoint does NOT enforce eligibility — the iOS wardrobe
    is currently the gatekeeper for which accessories can be unlocked
    when. When the achievement detection system ships, the eligibility
    check will move server-side and live in a service module that
    decides whether to call this same endpoint.
    """
    user_id = current_user.apple_user_id
    accessory_id = body.accessory_id

    # Idempotent check
    existing = await db.execute(
        select(UserMascotState).where(
            UserMascotState.user_id == user_id,
            UserMascotState.accessory_id == accessory_id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        state = await _load_state(db, user_id)
        return UnlockResponse(newly_unlocked=False, state=state)

    db.add(
        UserMascotState(
            user_id=user_id,
            accessory_id=accessory_id,
            unlocked_at=utcnow_naive(),
            equipped=False,
        )
    )
    await db.commit()
    logger.info(
        "Mascot unlock (manual): user=%s accessory=%s",
        user_id[:12] if user_id else "?",
        accessory_id,
    )

    state = await _load_state(db, user_id)
    return UnlockResponse(newly_unlocked=True, state=state)
