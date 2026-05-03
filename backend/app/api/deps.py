"""FastAPI dependencies, primary entry point for authenticated routes.

Usage in routers:

    from app.api.deps import CurrentUser

    @router.get("/api/dashboard")
    async def dashboard(user: CurrentUser, db: AsyncSession = Depends(get_db)):
        # user is a fully-loaded User row, verified and active
        ...

The `get_current_user` dependency:
1. Extracts the bearer token from the Authorization header
2. Verifies the JWT signature + claims (HS256, aud, iss, exp, typ)
3. Loads the User row from DB (for is_active check + up-to-date data)
4. Returns the User or raises 401

See `app/core/security.py` for token issuance and the matching decode logic.
"""

from __future__ import annotations

from typing import Annotated

import logging

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import decode_access_token
from app.database import get_db
from app.models.user import User

logger = logging.getLogger("meld.auth")

# `auto_error=True` → FastAPI returns 403 automatically if the header is missing.
# We override that with our own 401 below so the error shape is consistent.
_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Resolve the authenticated user for the current request.

    Raises 401 on any failure: missing header, invalid token, inactive user.
    """
    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(creds.credentials)
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    apple_user_id = payload.get("sub")
    if not apple_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(select(User).where(User.apple_user_id == apple_user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


# Convenience type alias so routers can write `user: CurrentUser` in signatures
# without importing Depends + the dependency function separately.
CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_admin_user(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Resolve the authenticated user AND require they're in ADMIN_USER_IDS.

    Comma-separated allow-list lives in `settings.admin_user_ids`. Empty list
    means no admin endpoints are reachable (returns 403 for everyone). In
    production, set to Brock's apple_user_id only.

    Why this dep exists: the 2026-04-29 audit found `/api/insights/admin/rollback`
    accepted any signed-in user, meaning any beta tester could swap the active
    CoreML ranker model. Now gated.
    """
    allow_list = [
        uid.strip() for uid in (settings.admin_user_ids or "").split(",") if uid.strip()
    ]
    if user.apple_user_id not in allow_list:
        # Log the attempt for forensics. Do not include token contents.
        logger.warning(
            "admin endpoint denied: user=%s allow_list_size=%d",
            user.apple_user_id,
            len(allow_list),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


# Same shape as CurrentUser, but only resolves for admins. Endpoints gated by
# CurrentAdminUser must NEVER also accept CurrentUser as an alternate path.
CurrentAdminUser = Annotated[User, Depends(get_current_admin_user)]
