"""Garmin authentication endpoints.

SSO-based auth via garminconnect library (username/password).
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.garmin import GarminToken
from app.services.garmin import GarminClient

logger = logging.getLogger("meld.garmin_auth")

router = APIRouter(prefix="/auth/garmin", tags=["auth"])

USER_ID = "default"


class GarminLoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login_garmin(
    request: GarminLoginRequest, db: AsyncSession = Depends(get_db)
):
    """Authenticate with Garmin Connect."""
    client = GarminClient()
    try:
        result = await client.login(request.username, request.password)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Garmin login failed: {str(e)}")

    token = GarminToken(
        user_id=USER_ID,
        username=request.username,
        session_data=request.password,  # Stored for re-login; garminconnect needs credentials
    )
    db.add(token)
    await db.commit()

    logger.info("Garmin connected for user %s", USER_ID)
    return {"status": "connected"}


@router.get("/status")
async def garmin_status(db: AsyncSession = Depends(get_db)):
    """Check if Garmin is connected."""
    result = await db.execute(
        select(GarminToken).where(GarminToken.user_id == USER_ID).limit(1)
    )
    token = result.scalar_one_or_none()
    return {"connected": token is not None, "username": token.username if token else None}
