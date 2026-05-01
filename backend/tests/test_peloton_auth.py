"""Tests for `POST /auth/peloton/login`.

MEL-44 part 2: the route now stores the user's password (encrypted at rest
via Fernet) on the PelotonToken row so scheduled syncs can re-login. These
tests pin the round-trip and the auth gate.

Run: cd backend && uv run python -m pytest tests/test_peloton_auth.py -v
"""

import os
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-peloton-auth-tests")
os.environ.setdefault(
    "ENCRYPTION_KEY", "T0TXLkHFSeZRYGIIejSFVkhQrvRE-bWLkwXSkkdWiKQ="
)

from app.core.security import create_access_token
from app.database import Base, get_db
from app.main import app
from app.models.peloton import PelotonToken
from app.models.user import User


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


async def _seed_authed_user(db_session, apple_user_id: str = "001234.peloton.0001") -> tuple[User, str]:
    """Create a User row + a fresh JWT for them."""
    user = User(
        apple_user_id=apple_user_id,
        email="test@example.com",
        name="Test User",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    token, _ = create_access_token(apple_user_id)
    return user, token


# ── Auth gate ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_login_unauthed_returns_401(client):
    """No Authorization header -> 401 (CurrentUser guard fires first)."""
    resp = await client.post(
        "/auth/peloton/login",
        json={"username": "x", "password": "y"},
    )
    assert resp.status_code == 401


# ── Successful login persists encrypted password ─────────────────────────


@pytest.mark.asyncio
async def test_login_success_persists_encrypted_password(client, db_session):
    _, jwt_token = await _seed_authed_user(db_session, "001234.peloton-ok.0001")

    fake_login = AsyncMock(return_value={"session_id": "oauth", "user_id": "p-uid-1"})
    with patch("app.routers.peloton_auth.PelotonClient") as fake_cls:
        fake_cls.return_value.login = fake_login

        resp = await client.post(
            "/auth/peloton/login",
            headers={"Authorization": f"Bearer {jwt_token}"},
            json={"username": "u@example.com", "password": "the-secret-pw"},
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "connected"

    # PelotonToken row exists for this user
    db_session.expire_all()
    row = (
        await db_session.execute(
            select(PelotonToken).where(PelotonToken.user_id == "001234.peloton-ok.0001")
        )
    ).scalar_one()
    # Username and password round-trip (EncryptedString decrypts on read)
    assert row.username == "u@example.com"
    assert row.password == "the-secret-pw"
    assert row.peloton_user_id == "p-uid-1"


# ── Login failure surfaces 401 ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_login_invalid_credentials_returns_401(client, db_session):
    _, jwt_token = await _seed_authed_user(db_session, "001234.peloton-bad.0001")

    fake_login = AsyncMock(side_effect=ValueError("bad creds"))
    with patch("app.routers.peloton_auth.PelotonClient") as fake_cls:
        fake_cls.return_value.login = fake_login

        resp = await client.post(
            "/auth/peloton/login",
            headers={"Authorization": f"Bearer {jwt_token}"},
            json={"username": "u@example.com", "password": "wrong"},
        )

    assert resp.status_code == 401
    # No row should be persisted on failure
    db_session.expire_all()
    rows = (
        await db_session.execute(
            select(PelotonToken).where(PelotonToken.user_id == "001234.peloton-bad.0001")
        )
    ).scalars().all()
    assert rows == []


# ── Reconnect replaces old token ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_login_replaces_existing_token(client, db_session):
    """Re-login with new credentials replaces the prior token row."""
    apple_id = "001234.peloton-replace.0001"
    _, jwt_token = await _seed_authed_user(db_session, apple_id)

    # Pre-seed an old token
    db_session.add(
        PelotonToken(
            user_id=apple_id,
            peloton_user_id="old-uid",
            session_id="oauth",
            username="old@example.com",
            password="old-password",
        )
    )
    await db_session.commit()

    fake_login = AsyncMock(return_value={"session_id": "oauth", "user_id": "new-uid"})
    with patch("app.routers.peloton_auth.PelotonClient") as fake_cls:
        fake_cls.return_value.login = fake_login

        resp = await client.post(
            "/auth/peloton/login",
            headers={"Authorization": f"Bearer {jwt_token}"},
            json={"username": "new@example.com", "password": "new-password"},
        )

    assert resp.status_code == 200
    db_session.expire_all()
    rows = (
        await db_session.execute(
            select(PelotonToken).where(PelotonToken.user_id == apple_id)
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].username == "new@example.com"
    assert rows[0].password == "new-password"
    assert rows[0].peloton_user_id == "new-uid"
