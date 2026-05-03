"""Regression tests for /health/canary.

Pinned in MEL-45 part 2 to prevent the PHI-leak from coming back. Pre-MEL-45
the endpoint returned the first active user's reconciled health metrics,
which was a no-auth endpoint exposing arbitrary users' sleep/HRV/RHR. The
fix is aggregate-only, these tests assert the response shape never
contains per-user health data again.

Run: cd backend && uv run python -m pytest tests/test_health_canary.py -v
"""

import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("ENCRYPTION_KEY", "T0TXLkHFSeZRYGIIejSFVkhQrvRE-bWLkwXSkkdWiKQ=")
os.environ.setdefault("ANTHROPIC_API_KEY", "fake-key-tests-dont-call-anthropic")

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.time import utcnow_naive
from app.database import Base, get_db
from app.main import app
from app.models.health import OuraToken, SleepRecord
from app.models.user import User


@pytest_asyncio.fixture
async def empty_db():
    """In-memory SQLite with tables but no rows."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded_db():
    """In-memory SQLite with one active user, a fresh sleep record, and one Oura token."""
    from datetime import timedelta

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        user = User(apple_user_id="apple-test-1", is_active=True)
        session.add(user)
        # Fresh sleep record (synced 1 hour ago)
        session.add(
            SleepRecord(
                user_id="apple-test-1",
                date="2026-04-30",
                synced_at=utcnow_naive() - timedelta(hours=1),
            )
        )
        # Oura connection
        session.add(
            OuraToken(
                user_id="apple-test-1",
                access_token="encrypted-test-token",
                refresh_token="encrypted-test-refresh",
                expires_at=utcnow_naive() + timedelta(days=30),
            )
        )
        await session.commit()
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_canary_returns_aggregate_shape_only(empty_db):
    """No PHI leak: response keys are aggregate counts, never per-user health metrics."""

    async def _override_db():
        yield empty_db

    app.dependency_overrides[get_db] = _override_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/health/canary")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    # Aggregate-only contract
    assert set(body.keys()) == {
        "status",
        "active_users",
        "users_with_data_24h",
        "active_oura_connections",
    }
    # Explicitly NOT the legacy per-user keys
    assert "checks" not in body
    assert "sleep_efficiency" not in body
    assert "hrv_average" not in body
    assert "data_sources" not in body


@pytest.mark.asyncio
async def test_canary_no_auth_required(empty_db):
    """Endpoint must remain public so uptime monitors can hit it without a token."""

    async def _override_db():
        yield empty_db

    app.dependency_overrides[get_db] = _override_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # No Authorization header
            resp = await client.get("/api/health/canary")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_canary_empty_db_is_degraded(empty_db):
    """No users, no data: status is 'degraded', counts are zero."""

    async def _override_db():
        yield empty_db

    app.dependency_overrides[get_db] = _override_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/health/canary")
    finally:
        app.dependency_overrides.clear()

    body = resp.json()
    assert body["status"] == "degraded"
    assert body["active_users"] == 0
    assert body["users_with_data_24h"] == 0
    assert body["active_oura_connections"] == 0


@pytest.mark.asyncio
async def test_canary_seeded_db_is_ok_and_counts(seeded_db):
    """One user + fresh sleep + one Oura token: status 'ok', counts are 1."""

    async def _override_db():
        yield seeded_db

    app.dependency_overrides[get_db] = _override_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/health/canary")
    finally:
        app.dependency_overrides.clear()

    body = resp.json()
    assert body["status"] == "ok"
    assert body["active_users"] == 1
    assert body["users_with_data_24h"] == 1
    assert body["active_oura_connections"] == 1


@pytest.mark.asyncio
async def test_canary_stale_sleep_record_does_not_count_as_fresh(empty_db):
    """A sleep record older than 24h must not contribute to users_with_data_24h."""
    from datetime import timedelta

    user = User(apple_user_id="apple-stale-1", is_active=True)
    empty_db.add(user)
    empty_db.add(
        SleepRecord(
            user_id="apple-stale-1",
            date="2026-04-29",
            # 25 hours ago, outside the freshness window
            synced_at=utcnow_naive() - timedelta(hours=25),
        )
    )
    await empty_db.commit()

    async def _override_db():
        yield empty_db

    app.dependency_overrides[get_db] = _override_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/health/canary")
    finally:
        app.dependency_overrides.clear()

    body = resp.json()
    assert body["active_users"] == 1  # user counts
    assert body["users_with_data_24h"] == 0  # but stale data doesn't
    assert body["status"] == "degraded"
