"""Tests for the Oura OAuth callback's deep-link redirect contract.

Pre-fix the callback returned `{"status": "connected"}` JSON, leaving the
user stranded on a JSON page in iPhone Safari after OAuth. Post-fix the
callback redirects to `meld://oura/connected` (or `meld://oura/error?...`)
so iOS auto-bounces back into the Meld app.

These tests pin the redirect contract and the persistence of `oura_user_id`
on the success path.

Run: cd backend && uv run python -m pytest tests/test_auth_oura_callback.py -v
"""

import os
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-oura-callback")
os.environ.setdefault(
    "ENCRYPTION_KEY", "T0TXLkHFSeZRYGIIejSFVkhQrvRE-bWLkwXSkkdWiKQ="
)

from app.database import Base, get_db
from app.main import app
from app.models.health import OuraToken
from app.models.user import User


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
    # follow_redirects=False so we can assert the 307 + Location header
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


# ── User cancelled on Oura's consent screen ──────────────────────────────


@pytest.mark.asyncio
async def test_callback_user_cancelled_redirects_with_access_denied(client):
    """Oura sends ?error=access_denied (no code) when the user taps Cancel.
    We don't 422 the user — bounce back to meld://oura/error?reason=access_denied
    so the iOS app can show the right alert."""
    resp = await client.get(
        "/auth/oura/callback",
        params={"error": "access_denied", "state": "001234.cancelled.0001"},
    )
    assert resp.status_code in (302, 307)
    assert resp.headers["location"] == "meld://oura/error?reason=access_denied"


@pytest.mark.asyncio
async def test_callback_missing_code_and_no_error_redirects_to_missing_code(client):
    """Malformed Oura redirect (no code, no error param) -> generic missing_code reason."""
    resp = await client.get(
        "/auth/oura/callback",
        params={"state": "001234.malformed.0001"},
    )
    assert resp.status_code in (302, 307)
    assert resp.headers["location"] == "meld://oura/error?reason=missing_code"


# ── Invalid state -> error deep link ─────────────────────────────────────


@pytest.mark.asyncio
async def test_callback_invalid_state_redirects_to_error_deep_link(client):
    """No matching User row -> redirect to meld://oura/error?reason=invalid_state.

    Pre-fix this returned 400 JSON; that stranded iPhone Safari users on a
    text page. Now we always deep-link out so the iOS handler can show its
    own alert.
    """
    resp = await client.get(
        "/auth/oura/callback",
        params={"code": "fake-code", "state": "001234.no-such-user.0001"},
    )
    assert resp.status_code in (302, 307)
    assert resp.headers["location"] == "meld://oura/error?reason=invalid_state"


# ── Exchange-code failure -> error deep link ─────────────────────────────


@pytest.mark.asyncio
async def test_callback_exchange_failure_redirects_to_error_deep_link(client, db_session):
    """Oura's token endpoint returns 5xx / network error -> error deep link."""
    db_session.add(User(apple_user_id="001234.exchange-fail.0001", is_active=True))
    await db_session.commit()

    fake_exchange = AsyncMock(side_effect=httpx.ConnectError("oura down"))
    with patch("app.routers.auth.OuraClient") as fake_cls:
        instance = fake_cls.return_value
        instance.exchange_code = fake_exchange
        instance.get_personal_info = AsyncMock(return_value={})

        resp = await client.get(
            "/auth/oura/callback",
            params={"code": "fake-code", "state": "001234.exchange-fail.0001"},
        )

    assert resp.status_code in (302, 307)
    assert resp.headers["location"] == "meld://oura/error?reason=exchange_failed"

    # No token persisted on failure
    db_session.expire_all()
    rows = (
        await db_session.execute(
            select(OuraToken).where(OuraToken.user_id == "001234.exchange-fail.0001")
        )
    ).scalars().all()
    assert rows == []


# ── Success -> connected deep link + token persisted ─────────────────────


@pytest.mark.asyncio
async def test_callback_success_redirects_to_connected_deep_link(client, db_session):
    """Happy path: token persisted and Safari bounces back to meld://oura/connected."""
    db_session.add(User(apple_user_id="001234.oura-ok.0001", is_active=True))
    await db_session.commit()

    fake_token_data = {
        "access_token": "access-abc",
        "refresh_token": "refresh-xyz",
        "expires_in": 86400,
    }
    fake_personal = {"id": "oura-uid-9000", "age": 35}

    with patch("app.routers.auth.OuraClient") as fake_cls:
        # Two instances are constructed in the route (one for exchange_code,
        # one for personal_info). Both come from the same MagicMock.return_value
        # by default.
        instance = fake_cls.return_value
        instance.exchange_code = AsyncMock(return_value=fake_token_data)
        instance.get_personal_info = AsyncMock(return_value=fake_personal)

        resp = await client.get(
            "/auth/oura/callback",
            params={"code": "fake-code", "state": "001234.oura-ok.0001"},
        )

    assert resp.status_code in (302, 307)
    assert resp.headers["location"] == "meld://oura/connected"

    # Token persisted with oura_user_id
    db_session.expire_all()
    row = (
        await db_session.execute(
            select(OuraToken).where(OuraToken.user_id == "001234.oura-ok.0001")
        )
    ).scalar_one()
    assert row.access_token == "access-abc"
    assert row.refresh_token == "refresh-xyz"
    assert row.oura_user_id == "oura-uid-9000"


@pytest.mark.asyncio
async def test_callback_personal_info_failure_still_succeeds(client, db_session):
    """personal_info is best-effort. If it fails, we still persist the token
    (with NULL oura_user_id) and redirect to the success deep link. The
    webhook receiver's single-user fallback covers the gap."""
    db_session.add(User(apple_user_id="001234.no-personal.0001", is_active=True))
    await db_session.commit()

    fake_token_data = {
        "access_token": "access-abc",
        "refresh_token": "refresh-xyz",
        "expires_in": 86400,
    }

    with patch("app.routers.auth.OuraClient") as fake_cls:
        instance = fake_cls.return_value
        instance.exchange_code = AsyncMock(return_value=fake_token_data)
        instance.get_personal_info = AsyncMock(side_effect=httpx.ConnectError("info down"))

        resp = await client.get(
            "/auth/oura/callback",
            params={"code": "fake-code", "state": "001234.no-personal.0001"},
        )

    assert resp.status_code in (302, 307)
    assert resp.headers["location"] == "meld://oura/connected"

    db_session.expire_all()
    row = (
        await db_session.execute(
            select(OuraToken).where(OuraToken.user_id == "001234.no-personal.0001")
        )
    ).scalar_one()
    assert row.access_token == "access-abc"
    assert row.oura_user_id is None  # backfill on next sync
