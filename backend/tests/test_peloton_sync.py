"""Regression tests for `peloton_sync.sync_user_data`.

Until the architecture rework lands (Linear MEL-44), this function must:
  - return a structured status (not raise TypeError)
  - distinguish "no Peloton ever connected" from "connected but reauth needed"
  - not pretend to fetch workouts

The pre-PR shape (passing `session_id=` and `user_id=` into a no-arg
`PelotonClient.__init__`) was raising TypeError on every scheduled job for any
user who had connected. These tests pin the post-fix contract.

Run: cd backend && uv run pytest tests/test_peloton_sync.py -v
"""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-peloton-sync-tests")

from app.services.peloton_sync import sync_user_data


class _FakeToken:
    """Minimal stand-in for `PelotonToken`, just the fields ensure_valid_session reads."""

    def __init__(self, session_id: str = "oauth", peloton_user_id: str = "peloton-user-123"):
        self.session_id = session_id
        self.peloton_user_id = peloton_user_id


def _mock_db_returning(token: _FakeToken | None) -> AsyncMock:
    """Build an AsyncMock DB session whose `.execute(...)` returns a result that
    yields the given token (or None) from `scalar_one_or_none()`."""
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=token)
    db.execute = AsyncMock(return_value=result)
    return db


@pytest.mark.asyncio
async def test_sync_returns_error_when_no_token():
    """User has never connected Peloton → clean error, no exception."""
    db = _mock_db_returning(None)
    result = await sync_user_data(db, "user-abc")
    assert result["status"] == "error"
    assert "Connect your account" in result["message"]


@pytest.mark.asyncio
async def test_sync_returns_needs_reauth_when_token_present():
    """User has connected (any session_id, including the legacy "oauth"
    placeholder) → needs_reauth status, never TypeError."""
    db = _mock_db_returning(_FakeToken(session_id="oauth"))
    result = await sync_user_data(db, "user-abc")
    assert result["status"] == "needs_reauth"
    assert "reconnect" in result["message"].lower() or "reauth" in result["message"].lower()


@pytest.mark.asyncio
async def test_sync_does_not_raise_typeerror_with_legacy_token():
    """Regression: pre-PR, `PelotonClient(session_id=..., user_id=...)` raised
    TypeError because the constructor takes no args. Post-PR, the call site is
    gone and we cannot raise that specific failure mode. This pins it."""
    db = _mock_db_returning(_FakeToken(session_id="oauth", peloton_user_id="anything"))
    # Just must not raise
    result = await sync_user_data(db, "user-abc")
    assert isinstance(result, dict)
    assert "status" in result
