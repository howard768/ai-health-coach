"""User profile endpoints."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.health import OuraToken

logger = logging.getLogger("meld.user")

router = APIRouter(prefix="/api/user", tags=["user"])

USER_ID = "default"  # TODO: replace with real auth


class UserProfileResponse(BaseModel):
    name: str | None = None
    email: str | None = None
    age: int | None = None
    height_inches: int | None = None
    weight_lbs: float | None = None
    target_weight_lbs: float | None = None
    goals: list[str] = []
    training_experience: str | None = None
    training_days_per_week: int | None = None
    member_since: str | None = None
    data_sources: list[dict] = []


class UserProfileUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    age: int | None = None
    height_inches: int | None = None
    weight_lbs: float | None = None
    target_weight_lbs: float | None = None
    goals: list[str] | None = None
    training_experience: str | None = None
    training_days_per_week: int | None = None


@router.get("/profile", response_model=UserProfileResponse)
async def get_profile(db: AsyncSession = Depends(get_db)):
    """Get user profile with connected data sources."""
    result = await db.execute(
        select(User).where(User.apple_user_id == USER_ID)
    )
    user = result.scalar_one_or_none()

    # Check connected data sources
    oura_result = await db.execute(
        select(OuraToken).where(OuraToken.user_id == USER_ID).limit(1)
    )
    oura_token = oura_result.scalar_one_or_none()

    data_sources = []
    if oura_token:
        data_sources.append({
            "name": "Oura Ring",
            "connected": True,
            "last_synced": oura_token.created_at.isoformat() if oura_token.created_at else None,
        })

    if not user:
        return UserProfileResponse(data_sources=data_sources)

    import json
    goals = []
    if user.goals:
        try:
            goals = json.loads(user.goals) if isinstance(user.goals, str) else user.goals
        except (json.JSONDecodeError, TypeError):
            goals = []

    return UserProfileResponse(
        name=user.name,
        email=user.email,
        age=user.age,
        height_inches=user.height_inches,
        weight_lbs=user.weight_lbs,
        target_weight_lbs=user.target_weight_lbs,
        goals=goals,
        training_experience=user.training_experience,
        training_days_per_week=user.training_days_per_week,
        member_since=user.created_at.strftime("%B %Y") if user.created_at else None,
        data_sources=data_sources,
    )


@router.put("/profile", response_model=UserProfileResponse)
async def update_profile(
    update: UserProfileUpdate, db: AsyncSession = Depends(get_db)
):
    """Update user profile fields."""
    result = await db.execute(
        select(User).where(User.apple_user_id == USER_ID)
    )
    user = result.scalar_one_or_none()

    if not user:
        # Create user if doesn't exist
        import json
        user = User(
            apple_user_id=USER_ID,
            name=update.name,
            email=update.email,
            age=update.age,
            height_inches=update.height_inches,
            weight_lbs=update.weight_lbs,
            target_weight_lbs=update.target_weight_lbs,
            goals=json.dumps(update.goals) if update.goals else None,
            training_experience=update.training_experience,
            training_days_per_week=update.training_days_per_week,
        )
        db.add(user)
    else:
        import json
        if update.name is not None:
            user.name = update.name
        if update.email is not None:
            user.email = update.email
        if update.age is not None:
            user.age = update.age
        if update.height_inches is not None:
            user.height_inches = update.height_inches
        if update.weight_lbs is not None:
            user.weight_lbs = update.weight_lbs
        if update.target_weight_lbs is not None:
            user.target_weight_lbs = update.target_weight_lbs
        if update.goals is not None:
            user.goals = json.dumps(update.goals)
        if update.training_experience is not None:
            user.training_experience = update.training_experience
        if update.training_days_per_week is not None:
            user.training_days_per_week = update.training_days_per_week
        user.updated_at = datetime.utcnow()

    await db.commit()
    return await get_profile(db)
