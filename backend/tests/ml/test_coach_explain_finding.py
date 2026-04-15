"""End-to-end tests for POST /api/coach/explain-finding.

Uses FastAPI's AsyncClient. Stubs out CurrentUser + get_db deps via the
FastAPI dependency-override pattern. Mocks the Anthropic client at the
module level so no live LLM calls happen.

Run: ``cd backend && uv run python -m pytest tests/ml/test_coach_explain_finding.py -v``
"""

from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest
import pytest_asyncio

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("ENCRYPTION_KEY", "T0TXLkHFSeZRYGIIejSFVkhQrvRE-bWLkwXSkkdWiKQ=")
os.environ.setdefault("ANTHROPIC_API_KEY", "fake-key-tests-dont-call-anthropic")

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app
# Register ORM models before create_all.
from app.models import ml_baselines as _ml_baselines_models  # noqa: F401
from app.models import ml_features as _ml_features_models  # noqa: F401
from app.models import ml_insights as _ml_insights_models  # noqa: F401
from app.models.ml_insights import MLInsightCandidate
from app.models.user import User
from ml.narrate import translator as _translator


USER_ID = "apple-user-explain"


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def api_client(db):
    """Test client with auth + db stubbed and the Opus narrator patched.

    The narrator is patched to return canned text so tests do not hit the
    real Anthropic API. Tests that need specific narrator behavior can
    override the patched function per-test.
    """
    from app.api import deps

    db.add(User(apple_user_id=USER_ID, email="explain@test.com", is_active=True))
    await db.commit()

    async def _override_db():
        yield db

    async def _override_user():
        user = (
            await db.execute(select(User).where(User.apple_user_id == USER_ID))
        ).scalar_one()
        return user

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[deps.get_current_user] = _override_user

    async def fake_generate(request, client=None):
        return _translator.NarrationResult(
            text="Higher protein tends to mean longer deep sleep.",
            used_fallback=False,
            fallback_reason=None,
        )

    with patch.object(_translator, "generate_narration", side_effect=fake_generate):
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            yield client

    app.dependency_overrides.clear()


async def _seed_correlation_candidate(db, candidate_id: str = "cand-explain") -> None:
    db.add(
        MLInsightCandidate(
            id=candidate_id,
            user_id=USER_ID,
            kind="correlation",
            subject_metrics_json=json.dumps(["protein_intake", "deep_sleep_seconds"]),
            effect_size=0.55,
            confidence=0.95,
            novelty=1.0,
            recency_days=0,
            actionability_score=1.0,
            literature_support=True,
            directional_support=False,
            causal_support=False,
            payload_json=json.dumps(
                {
                    "source_metric": "protein_intake",
                    "target_metric": "deep_sleep_seconds",
                    "direction": "positive",
                    "pearson_r": 0.55,
                    "spearman_r": 0.5,
                    "sample_size": 60,
                    "confidence_tier": "literature_supported",
                    "literature_ref": "10.1007/s40279-014-0260-0",
                }
            ),
        )
    )
    await db.commit()


# ─────────────────────────────────────────────────────────────────────────
# Happy path
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_explain_finding_returns_narration_and_contributions(db, api_client):
    await _seed_correlation_candidate(db)

    resp = await api_client.post(
        "/api/coach/explain-finding",
        json={"insight_id": "cand-explain"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["insight_id"] == "cand-explain"
    assert body["kind"] == "correlation"
    assert body["narration"].startswith("Higher protein")
    assert body["narration_used_fallback"] is False
    # Correlation contributions include source/target.
    feature_names = [c["feature"] for c in body["contributions"]]
    assert any("protein_intake" in f for f in feature_names)
    assert any("deep_sleep_seconds" in f for f in feature_names)
    # Historical examples include literature + sample size.
    hist_kinds = [h["kind"] for h in body["historical_examples"]]
    assert "sample_size" in hist_kinds
    assert "literature" in hist_kinds


# ─────────────────────────────────────────────────────────────────────────
# Not found
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_explain_finding_404_on_unknown_insight(db, api_client):
    resp = await api_client.post(
        "/api/coach/explain-finding",
        json={"insight_id": "does-not-exist"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_explain_finding_404_on_other_users_insight(db, api_client):
    # Seed a candidate owned by a different user.
    db.add(
        MLInsightCandidate(
            id="cand-other",
            user_id="someone-else",
            kind="correlation",
            subject_metrics_json=json.dumps(["x", "y"]),
            effect_size=0.5,
            confidence=0.6,
            novelty=1.0,
            recency_days=0,
            actionability_score=0.5,
            literature_support=False,
            directional_support=False,
            causal_support=False,
            payload_json=json.dumps({"source_metric": "x", "target_metric": "y"}),
        )
    )
    await db.commit()

    resp = await api_client.post(
        "/api/coach/explain-finding",
        json={"insight_id": "cand-other"},
    )
    assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────
# Narration fallback surfaces in response
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_explain_finding_surfaces_fallback_flag(db):
    """When narration falls back to template, the response flags it."""
    from app.api import deps

    db.add(User(apple_user_id=USER_ID, email="fallback@test.com", is_active=True))
    await _seed_correlation_candidate(db, candidate_id="cand-fallback")

    async def _override_db():
        yield db

    async def _override_user():
        return (
            await db.execute(select(User).where(User.apple_user_id == USER_ID))
        ).scalar_one()

    async def fake_fallback(request, client=None):
        return _translator.NarrationResult(
            text=_translator._TEMPLATE_FALLBACK["correlation"],
            used_fallback=True,
            fallback_reason="voice_compliance",
        )

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[deps.get_current_user] = _override_user
    try:
        with patch.object(_translator, "generate_narration", side_effect=fake_fallback):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as client:
                resp = await client.post(
                    "/api/coach/explain-finding",
                    json={"insight_id": "cand-fallback"},
                )
        assert resp.status_code == 200
        body = resp.json()
        assert body["narration_used_fallback"] is True
        assert body["narration"] == _translator._TEMPLATE_FALLBACK["correlation"]
    finally:
        app.dependency_overrides.clear()
