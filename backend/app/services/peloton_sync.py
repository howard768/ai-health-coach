"""Peloton data sync service.

Status: BLOCKED on architecture rework (Linear MEL-44).

`PelotonClient` is built on `pylotoncycle.PylotonCycle` which authenticates via
username + password and does NOT expose a session token suitable for
persistence. `PelotonToken.session_id` stores a literal "oauth" placeholder
(see `peloton.py:51`), so the legacy call path here was passing
`session_id="oauth"` into a `PelotonClient.__init__` that takes no arguments —
every scheduled sync TypeError'd silently for any user who had connected.

Until we add encrypted credential storage to `PelotonToken` (or replace
pylotoncycle with a session-token-aware client), `sync_user_data` returns a
clean ``needs_reauth`` status instead of attempting and failing. The legacy
fetch + dedup + write logic is preserved in git history (last working shape:
HEAD~1 of branch claude/audit-pra-peloton-typerror).
"""

import logging

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.peloton import PelotonToken

logger = logging.getLogger("meld.peloton_sync")


async def ensure_valid_session(db: AsyncSession, user_id: str) -> tuple[str, str] | None:
    """Get the most recent Peloton token row, if any.

    Returns ``(session_id, peloton_user_id)`` or ``None``. Per the architecture
    note above, ``session_id`` is currently always the literal "oauth"
    placeholder; callers must NOT pass it to ``PelotonClient`` until the
    rework lands.
    """
    result = await db.execute(
        select(PelotonToken)
        .where(PelotonToken.user_id == user_id)
        .order_by(desc(PelotonToken.created_at))
        .limit(1)
    )
    token = result.scalar_one_or_none()
    if not token:
        return None
    return (token.session_id, token.peloton_user_id)


async def sync_user_data(db: AsyncSession, user_id: str) -> dict:
    """Return a clean reauth status until the architecture rework lands.

    Pre-rework, every scheduled call here raised `TypeError` because the
    constructor signature changed but the call site didn't. That spammed
    Sentry and produced no user-visible recovery path. Post-this-PR, scheduled
    syncs short-circuit with a structured status the scheduler can log
    without alerting.

    See module docstring + Linear MEL-44 for the rework scope.
    """
    session_info = await ensure_valid_session(db, user_id)
    if not session_info:
        return {"status": "error", "message": "No Peloton session. Connect your account."}

    logger.info(
        "Peloton sync deferred for user %s: legacy session unusable, reauth required",
        user_id,
    )
    return {
        "status": "needs_reauth",
        "message": "Peloton needs reauthentication; reconnect in Settings.",
    }
