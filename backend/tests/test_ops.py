"""Tests for the /ops/status endpoint.

Run: cd backend && uv run python -m pytest tests/test_ops.py -v
"""

import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("ENCRYPTION_KEY", "T0TXLkHFSeZRYGIIejSFVkhQrvRE-bWLkwXSkkdWiKQ=")
os.environ.setdefault("ANTHROPIC_API_KEY", "fake-key-tests-dont-call-anthropic")

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app
from app.models.notification import NotificationRecord


@pytest.mark.asyncio
async def test_ops_status_returns_200():
    """Ops status endpoint returns 200 with expected shape."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/ops/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("ok", "degraded")
    assert "scheduler_running" in data
    assert "sentry_enabled" in data
    assert isinstance(data["sentry_enabled"], bool)
    assert "jobs" in data
    assert isinstance(data["jobs"], list)
    assert "pipeline_freshness" in data
    assert "db_ok" in data
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_ops_status_has_pipeline_freshness_keys():
    """Pipeline freshness contains expected table references."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/ops/status")

    freshness = resp.json()["pipeline_freshness"]
    expected_keys = {
        "ml_features_latest",
        "ml_baselines_latest",
        "ml_insights_latest",
        "ml_synth_runs_latest",
        "user_correlations_latest",
        "notification_records_latest",
    }
    assert set(freshness.keys()) == expected_keys


@pytest.mark.asyncio
async def test_ops_status_no_auth_required():
    """Ops endpoint is public (no auth header needed)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/ops/status")

    # Should succeed without any Authorization header
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_ops_status_jobs_have_expected_fields():
    """Each job in the response has id, name, next_run, pending."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/ops/status")

    jobs = resp.json()["jobs"]
    if jobs:  # scheduler may or may not be running in test env
        job = jobs[0]
        assert "id" in job
        assert "name" in job
        assert "next_run" in job
        assert "pending" in job


# -- Freshness round-trip: verifies the per-table column map is correct. --


@pytest_asyncio.fixture
async def seeded_db():
    """In-memory SQLite with tables created and one NotificationRecord seeded."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        session.add(
            NotificationRecord(
                user_id="test-user",
                device_token_id=None,
                category="morning_brief",
                title="test",
                body="body",
            )
        )
        await session.commit()
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_notification_records_freshness_returns_iso_string(seeded_db):
    """After seeding a NotificationRecord, notification_records_latest is an
    ISO-8601 string, not None.

    Regression test for the pre-fix bug where ops.py queried
    MAX(updated_at) against notification_records (which uses sent_at). Every
    production freshness field was silently NULL because the column didn't
    exist. See _FRESHNESS_SOURCES in ops.py.
    """

    async def _override_db():
        yield seeded_db

    app.dependency_overrides[get_db] = _override_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/ops/status")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    freshness = resp.json()["pipeline_freshness"]
    assert freshness["notification_records_latest"] is not None
    # Should parse as ISO-8601.
    assert "T" in freshness["notification_records_latest"]
