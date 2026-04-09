"""Peloton authentication endpoints.

Session-cookie auth (NOT OAuth). User provides username/password,
we get a session_id from Peloton's API.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.peloton import PelotonToken
from app.services.peloton import PelotonClient

logger = logging.getLogger("meld.peloton_auth")

router = APIRouter(prefix="/auth/peloton", tags=["auth"])

USER_ID = "default"


class PelotonLoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login_peloton(
    request: PelotonLoginRequest, db: AsyncSession = Depends(get_db)
):
    """Authenticate with Peloton and store session."""
    client = PelotonClient()

    try:
        result = await client.login(request.username, request.password)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Peloton login failed: {str(e)}")

    # Store session
    token = PelotonToken(
        user_id=USER_ID,
        peloton_user_id=result["user_id"],
        session_id=result["session_id"],
        username=request.username,
    )
    db.add(token)
    await db.commit()

    logger.info("Peloton connected for user %s", USER_ID)
    return {"status": "connected", "peloton_user_id": result["user_id"]}


@router.get("/status")
async def peloton_status(db: AsyncSession = Depends(get_db)):
    """Check if Peloton is connected."""
    result = await db.execute(
        select(PelotonToken).where(PelotonToken.user_id == USER_ID).limit(1)
    )
    token = result.scalar_one_or_none()
    return {
        "connected": token is not None,
        "username": token.username if token else None,
    }
