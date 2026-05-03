"""Tests for the MEL-45 part 2 webhook routing rewrite.

Pre-MEL-45 the receiver always picked the first OuraToken regardless of
which Oura user the webhook was about, which silently mis-routed events
in multi-user mode. The new logic is 3-step:

  1. Look up `OuraToken WHERE oura_user_id == body.user_id`
  2. If no match AND there's exactly one token in the system, fall back
     (legacy single-user transition window)
  3. If no match AND multiple tokens exist, log + Sentry, return 200

These tests pin each step. They mock `sync_user_data` so no Oura HTTP
happens, and clear the per-user throttle map between tests.

Run: cd backend && uv run python -m pytest tests/test_webhooks_oura_routing.py -v
"""

import os
from datetime import timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# Required env BEFORE importing app modules.
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-webhook-tests")
os.environ.setdefault(
    "ENCRYPTION_KEY",
    "T0TXLkHFSeZRYGIIejSFVkhQrvRE-bWLkwXSkkdWiKQ=",
)
from app.core.time import utcnow_naive
from app.database import Base, get_db
from app.main import app
from app.models.health import OuraToken
from app.routers import webhooks as webhooks_module


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def test_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    SessionMaker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with SessionMaker() as session:
        yield session


@pytest_asyncio.fixture
async def client(test_engine):
    SessionMaker = async_sessionmaker(test_engine, expire_on_commit=False)

    async def override_get_db():
        async with SessionMaker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def clear_throttle_state():
    """Wipe the receiver's per-user-id throttle dict between tests so
    sequential tests for the same body.user_id don't 'throttle' each other."""
    if hasattr(webhooks_module.oura_webhook_receiver, "_last_sync_at"):
        webhooks_module.oura_webhook_receiver._last_sync_at.clear()
    yield


def _make_token(*, user_id: str, oura_user_id: str | None = None) -> OuraToken:
    return OuraToken(
        user_id=user_id,
        oura_user_id=oura_user_id,
        access_token="encrypted-test-token",
        refresh_token="encrypted-test-refresh",
        expires_at=utcnow_naive() + timedelta(days=30),
    )


# ── GET /api/webhooks/oura (verification handshake) ──────────────────────


@pytest.fixture
def configured_verification_token(monkeypatch):
    """Pin the verification token used by the webhook handler.

    Pydantic Settings reads env at import time, so setting OURA_WEBHOOK_VERIFICATION_TOKEN
    after module import has no effect, patch the helper instead. The handler
    rejects the handshake when our configured token is empty (dev default), so
    every verification test needs this fixture.
    """
    # `webhooks.py` does `from app.services.oura_webhooks import _verification_token`,
    # so the function is bound into the webhooks module namespace at import time.
    # Patch the BOUND name where the route handler reads it from.
    monkeypatch.setattr(
        webhooks_module, "_verification_token", lambda: "test-verification-token"
    )
    return "test-verification-token"


@pytest.mark.asyncio
async def test_get_verification_success_echoes_challenge(client, configured_verification_token):
    """Correct token + challenge -> echoes challenge."""
    resp = await client.get(
        "/api/webhooks/oura",
        params={"verification_token": configured_verification_token, "challenge": "abc123"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"challenge": "abc123"}


@pytest.mark.asyncio
async def test_get_verification_wrong_token_rejected(client, configured_verification_token):
    """Mismatched verification_token -> error response."""
    resp = await client.get(
        "/api/webhooks/oura",
        params={"verification_token": "WRONG-TOKEN", "challenge": "abc"},
    )
    body = resp.json()
    assert "error" in body
    assert "challenge" not in body


@pytest.mark.asyncio
async def test_get_verification_missing_challenge_rejected(client, configured_verification_token):
    """Missing challenge -> error (we never echo arbitrary bytes back)."""
    resp = await client.get(
        "/api/webhooks/oura",
        params={"verification_token": configured_verification_token},
    )
    body = resp.json()
    assert "error" in body


# ── POST /api/webhooks/oura, Step 1: oura_user_id match ────────────────


@pytest.mark.asyncio
async def test_post_routes_to_user_matching_oura_user_id(client, db_session, monkeypatch):
    """Body.user_id matches an OuraToken.oura_user_id -> sync that user."""
    db_session.add(_make_token(user_id="apple-A", oura_user_id="oura-A"))
    db_session.add(_make_token(user_id="apple-B", oura_user_id="oura-B"))
    await db_session.commit()

    sync_calls: list[str] = []

    async def fake_sync(_db, user_id: str):
        sync_calls.append(user_id)
        return {"status": "ok"}

    monkeypatch.setattr(webhooks_module, "sync_user_data", fake_sync)

    resp = await client.post(
        "/api/webhooks/oura",
        json={
            "event_type": "create",
            "data_type": "daily_sleep",
            "user_id": "oura-B",  # Should route to apple-B, NOT apple-A
        },
    )
    assert resp.status_code == 200
    assert sync_calls == ["apple-B"], (
        "Webhook for oura-B must route to apple-B (the matching token), "
        f"got sync called with {sync_calls}"
    )


# ── POST, Step 2: single-user fallback ─────────────────────────────────


@pytest.mark.asyncio
async def test_post_falls_back_to_single_token_when_unmatched(client, db_session, monkeypatch):
    """Single legacy user with NULL oura_user_id; webhook arrives with a body
    user_id we've never seen -> fallback to the only token (transition window)."""
    db_session.add(_make_token(user_id="legacy-apple", oura_user_id=None))
    await db_session.commit()

    sync_calls: list[str] = []

    async def fake_sync(_db, user_id: str):
        sync_calls.append(user_id)
        return {"status": "ok"}

    monkeypatch.setattr(webhooks_module, "sync_user_data", fake_sync)

    resp = await client.post(
        "/api/webhooks/oura",
        json={
            "event_type": "update",
            "data_type": "daily_readiness",
            "user_id": "oura-unknown-but-legacy",
        },
    )
    assert resp.status_code == 200
    assert sync_calls == ["legacy-apple"]


@pytest.mark.asyncio
async def test_post_no_users_returns_no_user(client):
    """Empty OuraToken table -> no_user (don't even attempt sync)."""
    resp = await client.post(
        "/api/webhooks/oura",
        json={
            "event_type": "create",
            "data_type": "daily_sleep",
            "user_id": "oura-X",
        },
    )
    assert resp.status_code == 200
    assert resp.json().get("status") == "no_user"


# ── POST, Step 3: multi-user no-match ──────────────────────────────────


@pytest.mark.asyncio
async def test_post_unmatched_in_multi_user_returns_no_match(
    client, db_session, monkeypatch
):
    """Two tokens, neither matches body.user_id -> no_match, no sync called."""
    db_session.add(_make_token(user_id="apple-A", oura_user_id="oura-A"))
    db_session.add(_make_token(user_id="apple-B", oura_user_id="oura-B"))
    await db_session.commit()

    sync_calls: list[str] = []

    async def fake_sync(_db, user_id: str):
        sync_calls.append(user_id)
        return {"status": "ok"}

    monkeypatch.setattr(webhooks_module, "sync_user_data", fake_sync)

    resp = await client.post(
        "/api/webhooks/oura",
        json={
            "event_type": "create",
            "data_type": "daily_sleep",
            "user_id": "oura-stranger",
        },
    )
    assert resp.status_code == 200
    assert resp.json().get("status") == "no_match"
    assert sync_calls == [], "no_match must NOT trigger a sync"


# ── POST, body shape validation ────────────────────────────────────────


@pytest.mark.asyncio
async def test_post_missing_required_fields_returns_invalid_payload(client):
    """Missing event_type/data_type/user_id -> invalid_payload, no sync."""
    resp = await client.post(
        "/api/webhooks/oura",
        json={"event_type": "create"},  # missing data_type + user_id
    )
    assert resp.status_code == 200
    assert resp.json().get("status") == "invalid_payload"


@pytest.mark.asyncio
async def test_post_malformed_json_returns_invalid_payload(client):
    """Non-JSON body -> invalid_payload (never 4xx; Oura's retry budget is scarce)."""
    resp = await client.post(
        "/api/webhooks/oura",
        content=b"not json at all",
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == 200
    assert resp.json().get("status") == "invalid_payload"
