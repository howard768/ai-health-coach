"""Peloton authentication endpoints.

Session-cookie auth (NOT OAuth). User provides username/password,
we exchange them for a session_id via Peloton's API and store ONLY
the session token — never the password.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.database import get_db
from app.models.peloton import PelotonToken
from app.services.peloton import PelotonClient, _PELOTON_FETCH_ERRORS

logger = logging.getLogger("meld.peloton_auth")

router = APIRouter(prefix="/auth/peloton", tags=["auth"])


class PelotonLoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login_peloton(
    request: PelotonLoginRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate with Peloton and store the session token for the current user."""
    client = PelotonClient()

    try:
        result = await client.login(request.username, request.password)
    except _PELOTON_FETCH_ERRORS as e:
        raise HTTPException(status_code=401, detail=f"Peloton login failed: {str(e)}")
    except ImportError:
        raise HTTPException(status_code=503, detail="pylotoncycle package not installed")

    user_id = current_user.apple_user_id
    # Delete any existing token for this user before inserting
    existing = await db.execute(select(PelotonToken).where(PelotonToken.user_id == user_id))
    for t in existing.scalars():
        await db.delete(t)

    token = PelotonToken(
        user_id=user_id,
        peloton_user_id=result["user_id"],
        session_id=result["session_id"],
        username=request.username,
    )
    db.add(token)
    await db.commit()

    logger.info("Peloton connected for user %s", user_id[:12])
    return {"status": "connected", "peloton_user_id": result["user_id"]}


@router.get("/status")
async def peloton_status(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Check if Peloton is connected for the current user."""
    result = await db.execute(
        select(PelotonToken).where(PelotonToken.user_id == current_user.apple_user_id).limit(1)
    )
    token = result.scalar_one_or_none()
    return {
        "connected": token is not None,
        "username": token.username if token else None,
    }
