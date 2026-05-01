"""Peloton authentication endpoints.

Peloton has no OAuth. The pylotoncycle library only takes username + password
(no persistable session token), so to keep syncing on a schedule we have to
hold the credentials and re-login on each cycle.

MEL-44 part 2: store the password (encrypted at rest via Fernet) on the token
row so `sync_user_data` can call `client.login(username, password)` fresh on
every scheduler tick. The legacy `session_id="oauth"` placeholder is kept on
the column for now (NOT NULL legacy schema), but is no longer load-bearing.
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
    """Authenticate with Peloton and persist credentials so scheduled syncs work."""
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
        session_id=result["session_id"],  # legacy placeholder, kept for column NOT-NULL
        password=request.password,  # encrypted at rest by EncryptedString TypeDecorator
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
