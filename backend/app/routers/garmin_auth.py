"""Garmin authentication endpoints.

SSO-based auth via garminconnect library (username/password flow). We exchange
the credentials for a serialized garth session (OAuth1 + OAuth2 tokens) and
store ONLY the session — never the password.

P0-2 fix: previously stored `session_data=request.password` (literal plaintext),
which was the worst security bug in the audit.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.database import get_db
from app.models.garmin import GarminToken
from app.services.garmin import GarminClient, _GARMIN_FETCH_ERRORS

logger = logging.getLogger("meld.garmin_auth")

router = APIRouter(prefix="/auth/garmin", tags=["auth"])


class GarminLoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login_garmin(
    request: GarminLoginRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate with Garmin Connect and store the session for the current user.

    The user's password is used once to log in and is then discarded. Only the
    serialized garth OAuth session is persisted.
    """
    client = GarminClient()
    try:
        result = await client.login(request.username, request.password)
    except _GARMIN_FETCH_ERRORS as e:
        raise HTTPException(status_code=401, detail=f"Garmin login failed: {str(e)}")
    except RuntimeError as e:
        # garminconnect library not installed
        raise HTTPException(status_code=503, detail=str(e))

    session_data = result.get("session_data")
    if not session_data:
        raise HTTPException(
            status_code=502,
            detail="Garmin login succeeded but session could not be serialized",
        )

    user_id = current_user.apple_user_id
    # Delete any existing token for this user before inserting
    existing = await db.execute(select(GarminToken).where(GarminToken.user_id == user_id))
    for t in existing.scalars():
        await db.delete(t)

    token = GarminToken(
        user_id=user_id,
        username=request.username,
        session_data=session_data,  # Serialized garth OAuth tokens — NOT the password
    )
    db.add(token)
    await db.commit()

    logger.info("Garmin connected for user %s", user_id[:12])
    return {"status": "connected"}


@router.get("/status")
async def garmin_status(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Check if Garmin is connected for the current user."""
    result = await db.execute(
        select(GarminToken).where(GarminToken.user_id == current_user.apple_user_id).limit(1)
    )
    token = result.scalar_one_or_none()
    return {"connected": token is not None, "username": token.username if token else None}
