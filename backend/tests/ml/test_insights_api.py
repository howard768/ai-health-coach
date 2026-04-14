"""Phase 4 end-to-end: ml.api.run_daily_insights + /api/insights/* router.

Exercises the full orchestration via the public ml.api boundary and the
HTTP endpoints the iOS client will call.

Run: ``cd backend && uv run python -m pytest tests/ml/test_insights_api.py -v``
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("ENCRYPTION_KEY", "T0TXLkHFSeZRYGIIejSFVkhQrvRE-bWLkwXSkkdWiKQ=")
os.environ.setdefault("ANTHROPIC_API_KEY", "fake-key-tests-dont-call-anthropic")
os.environ.setdefault("ML_ML_SHADOW_INSIGHT_CARD", "false")  # exercise non-shadow path for api tests

from datetime import date

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app
from app.models.correlation import UserCorrelation
# Register ORM models with Base.metadata before fixture create_all.
from app.models import ml_baselines as _ml_baselines_models  # noqa: F401
from app.models import ml_features as _ml_features_models  # noqa: F401
from app.models import ml_insights as _ml_insights_models  # noqa: F401
from app.models.ml_insights import MLRanking
from app.models.user import User
from ml import api as ml_api
from ml.config import get_ml_settings


USER_ID = "apple-user-test"


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


async def _seed_literature_corr(db: AsyncSession) -> None:
    """Seed a literature-supported correlation so the candidate is generated."""
    db.add(
        UserCorrelation(
            user_id=USER_ID,
            source_metric="protein_intake",
            target_metric="deep_sleep_seconds",
            lag_days=0,
            direction="positive",
            pearson_r=0.55,
            spearman_r=0.5,
            p_value=0.001,
            fdr_adjusted_p=0.01,
            sample_size=60,
            strength=0.55,
            confidence_tier="literature_supported",
            literature_match=True,
            literature_ref="10.1007/s40279-014-0260-0",
            effect_size_description="Higher protein tends to be associated with longer deep sleep.",
        )
    )
    await db.flush()


# ─────────────────────────────────────────────────────────────────────────
# ml.api.run_daily_insights (public boundary)
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_daily_insights_generates_and_ranks(db):
    await _seed_literature_corr(db)

    report = await ml_api.run_daily_insights(db, USER_ID)
    assert report.user_id == USER_ID
    assert report.candidates_generated == 1
    assert report.rankings_written == 1
    assert report.top_candidate_id is not None

    rows = (
        await db.execute(select(MLRanking).where(MLRanking.user_id == USER_ID))
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].rank == 1
    assert rows[0].was_shown is False


@pytest.mark.asyncio
async def test_run_daily_insights_is_idempotent(db):
    await _seed_literature_corr(db)

    r1 = await ml_api.run_daily_insights(db, USER_ID)
    r2 = await ml_api.run_daily_insights(db, USER_ID)

    rows = (
        await db.execute(select(MLRanking).where(MLRanking.user_id == USER_ID))
    ).scalars().all()
    assert len(rows) == 1
    assert r1.top_candidate_id == r2.top_candidate_id
    # Second run is a no-op: materialize_daily_ranking sees existing slate and returns [].
    assert r2.rankings_written == 0


@pytest.mark.asyncio
async def test_run_daily_insights_no_data_graceful(db):
    """No upstream -> 0 candidates, 0 rankings, no crash."""
    report = await ml_api.run_daily_insights(db, USER_ID)
    assert report.candidates_generated == 0
    assert report.rankings_written == 0
    assert report.top_candidate_id is None


# ─────────────────────────────────────────────────────────────────────────
# HTTP layer: /api/insights/daily + feedback
# ─────────────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def api_client(db):
    """FastAPI test client with auth stubbed out.

    Overrides ``get_db`` to hand back the test session, and overrides the
    ``CurrentUser`` dependency so we skip JWT plumbing for Phase 4 tests.
    Dedicated auth tests live in tests/test_auth.py.
    """
    from app.api import deps

    # Ensure the user row exists so any downstream code that joins on it works.
    db.add(
        User(
            apple_user_id=USER_ID,
            email="test@example.com",
            is_active=True,
        )
    )
    await db.commit()

    async def _override_db():
        yield db

    async def _override_user():
        user = (await db.execute(select(User).where(User.apple_user_id == USER_ID))).scalar_one()
        return user

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[deps.get_current_user] = _override_user

    # Clear the ml settings cache so the ML_ML_SHADOW_INSIGHT_CARD env var above is picked up.
    get_ml_settings.cache_clear()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    app.dependency_overrides.clear()
    get_ml_settings.cache_clear()


@pytest.mark.asyncio
async def test_get_daily_insight_returns_has_card_false_when_no_candidates(db, api_client):
    """No rankings exist -> 200 with has_card=false, reason=no_candidate_today."""
    resp = await api_client.get("/api/insights/daily")
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_card"] is False
    assert body["reason"] == "no_candidate_today"


@pytest.mark.asyncio
async def test_get_daily_insight_returns_top_card_when_ranking_exists(db, api_client):
    """Seed a candidate+ranking, hit the endpoint, expect the top card back
    and was_shown flipped to True."""
    await _seed_literature_corr(db)
    await ml_api.run_daily_insights(db, USER_ID)
    await db.commit()

    resp = await api_client.get("/api/insights/daily")
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_card"] is True
    card = body["card"]
    assert card["kind"] == "correlation"
    assert "subject_metrics" in card
    assert card["literature_support"] is True
    # Side-effect: was_shown flipped.
    row = (await db.execute(select(MLRanking).where(MLRanking.user_id == USER_ID))).scalar_one()
    assert row.was_shown is True
    assert row.shown_at is not None


@pytest.mark.asyncio
async def test_post_feedback_updates_ranking(db, api_client):
    await _seed_literature_corr(db)
    await ml_api.run_daily_insights(db, USER_ID)
    await db.commit()

    # Read to get ranking_id (and flip was_shown).
    get_resp = await api_client.get("/api/insights/daily")
    ranking_id = get_resp.json()["card"]["ranking_id"]

    post_resp = await api_client.post(
        f"/api/insights/{ranking_id}/feedback",
        json={"feedback": "thumbs_up"},
    )
    assert post_resp.status_code == 200
    assert post_resp.json() == {"ok": True}

    row = (await db.execute(select(MLRanking).where(MLRanking.id == ranking_id))).scalar_one()
    assert row.feedback == "thumbs_up"
    assert row.feedback_at is not None


@pytest.mark.asyncio
async def test_post_feedback_rejects_other_users_ranking(db, api_client):
    """Writing feedback to someone else's ranking -> 403."""
    # Seed a ranking for a DIFFERENT user.
    db.add(
        MLRanking(
            user_id="someone-else",
            surface_date=date.today().isoformat(),
            candidate_id="abc123",
            rank=1,
            score=0.8,
            ranker_version="heuristic-1.0.0",
            was_shown=True,
        )
    )
    await db.commit()
    other_ranking = (
        await db.execute(select(MLRanking).where(MLRanking.user_id == "someone-else"))
    ).scalar_one()

    resp = await api_client.post(
        f"/api/insights/{other_ranking.id}/feedback",
        json={"feedback": "thumbs_down"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_post_feedback_invalid_value_rejected(db, api_client):
    resp = await api_client.post(
        "/api/insights/999/feedback", json={"feedback": "love_it"}
    )
    # Pydantic Literal validation bounces before the 404 path.
    assert resp.status_code == 422
