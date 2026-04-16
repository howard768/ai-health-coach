"""Tests for the /ops/status endpoint.

Run: cd backend && uv run python -m pytest tests/test_ops.py -v
"""

import os

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("ENCRYPTION_KEY", "T0TXLkHFSeZRYGIIejSFVkhQrvRE-bWLkwXSkkdWiKQ=")
os.environ.setdefault("ANTHROPIC_API_KEY", "fake-key-tests-dont-call-anthropic")

from app.main import app


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
