"""Legacy Oura OAuth callback endpoints.

Oura uses a browser-redirect OAuth flow, so we can't use the normal bearer
auth dependency. Instead we pass the Meld user's apple_user_id through the
OAuth `state` parameter — Oura echoes it back on the callback, and we use
it to attach the resulting token to the right user.

The state is validated against an existing user row on return. This means
an attacker can't use the endpoint to attach Oura tokens to users they
don't control, because the user must have already completed Sign in with
Apple to exist in the users table.
"""

import logging
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.health import OuraToken
from app.models.user import User
from app.services.oura import OuraClient
from app.core.time import utcnow_naive

logger = logging.getLogger("meld.auth_oura")

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/oura")
async def oura_auth(
    state: str = Query(..., description="apple_user_id of the authenticated user initiating OAuth"),
):
    """Redirect the user to Oura's OAuth authorization page.

    `state` must be the caller's apple_user_id. The iOS client fetches it
    from the Keychain (or passes it in the URL when opening Safari). Oura
    will echo this back to the callback so we know which Meld user to
    attach the resulting token to.
    """
    client = OuraClient()
    # Append state to Oura's authorize URL
    auth_url = client.get_auth_url()
    separator = "&" if "?" in auth_url else "?"
    return RedirectResponse(url=f"{auth_url}{separator}state={state}")


@router.get("/oura/callback")
async def oura_callback(
    code: str,
    state: str = Query(..., description="apple_user_id echoed back from /auth/oura"),
    db: AsyncSession = Depends(get_db),
):
    """Handle Oura OAuth callback — exchange code for tokens, attach to user."""
    # Validate state points to a real user
    result = await db.execute(select(User).where(User.apple_user_id == state))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=400,
            detail="Invalid state parameter — user not found",
        )

    client = OuraClient()
    token_data = await client.exchange_code(code)

    # MEL-45 part 2: capture Oura's user ID so the webhook receiver can route
    # incoming events to the correct Meld user. Best-effort — if personal_info
    # fails (network, Oura down), store NULL and let sync_user_data backfill
    # on the next sync. Webhooks will fall back to the single-user path until
    # the column is populated.
    oura_user_id: str | None = None
    try:
        info_client = OuraClient(access_token=token_data["access_token"])
        info = await info_client.get_personal_info()
        oura_user_id = info.get("id")
        if not oura_user_id:
            logger.warning(
                "Oura personal_info returned no `id` field for apple_user=%s; "
                "webhook routing will use single-user fallback until next sync backfills",
                state[:12] + "...",
            )
    except (httpx.HTTPError, ValueError, KeyError) as e:
        logger.warning(
            "Oura personal_info fetch failed during connect for apple_user=%s: %s. "
            "Storing token without oura_user_id; sync will backfill later.",
            state[:12] + "...", e,
        )

    # Delete any existing Oura token for this user before inserting
    existing = await db.execute(select(OuraToken).where(OuraToken.user_id == state))
    for t in existing.scalars():
        await db.delete(t)

    oura_token = OuraToken(
        user_id=state,
        oura_user_id=oura_user_id,
        access_token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token", ""),
        expires_at=utcnow_naive() + timedelta(seconds=token_data.get("expires_in", 86400)),
    )
    db.add(oura_token)
    await db.commit()

    return {"status": "connected", "message": "Oura Ring connected successfully"}
