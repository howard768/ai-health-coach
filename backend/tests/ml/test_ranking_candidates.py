"""Phase 4 candidate normalization tests.

Covers: correlation -> candidate, anomaly -> candidate, id determinism,
novelty scoring, actionability mapping, and end-to-end upsert to
``ml_insight_candidates``.

Run: ``cd backend && uv run python -m pytest tests/ml/test_ranking_candidates.py -v``
"""

from __future__ import annotations

import json
import os

import pytest
import pytest_asyncio

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("ENCRYPTION_KEY", "T0TXLkHFSeZRYGIIejSFVkhQrvRE-bWLkwXSkkdWiKQ=")
os.environ.setdefault("ANTHROPIC_API_KEY", "fake-key-tests-dont-call-anthropic")

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models.correlation import UserCorrelation
# Register ORM models with Base.metadata before fixture create_all.
from app.models import ml_baselines as _ml_baselines_models  # noqa: F401
from app.models import ml_features as _ml_features_models  # noqa: F401
from app.models import ml_insights as _ml_insights_models  # noqa: F401
from app.models.ml_baselines import MLAnomaly
from app.models.ml_insights import MLInsightCandidate, MLRanking
from ml.ranking import candidates as cand_mod


USER = "u-candidates"
TODAY = date.today()


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


# ─────────────────────────────────────────────────────────────────────────
# make_candidate_id determinism
# ─────────────────────────────────────────────────────────────────────────


def test_make_candidate_id_is_deterministic():
    a = cand_mod.make_candidate_id("u1", "correlation", "steps", "sleep_efficiency", "0")
    b = cand_mod.make_candidate_id("u1", "correlation", "steps", "sleep_efficiency", "0")
    assert a == b
    assert len(a) == 24


def test_make_candidate_id_differs_on_different_subject():
    a = cand_mod.make_candidate_id("u1", "correlation", "steps", "sleep_efficiency", "0")
    b = cand_mod.make_candidate_id("u1", "correlation", "protein_g", "sleep_efficiency", "0")
    assert a != b


def test_make_candidate_id_differs_on_different_user():
    a = cand_mod.make_candidate_id("u1", "correlation", "steps", "sleep_efficiency", "0")
    b = cand_mod.make_candidate_id("u2", "correlation", "steps", "sleep_efficiency", "0")
    assert a != b


# ─────────────────────────────────────────────────────────────────────────
# Correlation -> candidate
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_developing_correlation_surfaces_as_candidate(db):
    """A UserCorrelation at 'developing' tier becomes a candidate."""
    db.add(
        UserCorrelation(
            user_id=USER,
            source_metric="steps",
            target_metric="sleep_efficiency",
            lag_days=0,
            direction="positive",
            pearson_r=0.7,
            spearman_r=0.65,
            p_value=0.01,
            fdr_adjusted_p=0.05,
            sample_size=35,
            strength=0.7,
            confidence_tier="developing",
            literature_match=False,
            effect_size_description="...",
        )
    )
    await db.flush()

    candidates = await cand_mod.generate_candidates(db, USER, TODAY)
    corr = [c for c in candidates if c.kind == "correlation"]
    assert len(corr) == 1
    c = corr[0]
    assert c.effect_size == pytest.approx(0.7)
    assert c.confidence == 0.60  # developing
    assert c.actionability_score == 1.0  # steps is a modifiable behavior
    assert c.literature_support is False


@pytest.mark.asyncio
async def test_emerging_correlation_is_not_surfaced(db):
    """Below 'developing', the candidate is not included."""
    db.add(
        UserCorrelation(
            user_id=USER,
            source_metric="steps",
            target_metric="sleep_efficiency",
            lag_days=0,
            direction="positive",
            pearson_r=0.4,
            spearman_r=0.38,
            p_value=0.04,
            fdr_adjusted_p=0.15,
            sample_size=20,
            strength=0.4,
            confidence_tier="emerging",
            literature_match=False,
            effect_size_description="...",
        )
    )
    await db.flush()

    candidates = await cand_mod.generate_candidates(db, USER, TODAY)
    assert not any(c.kind == "correlation" for c in candidates)


@pytest.mark.asyncio
async def test_literature_supported_correlation_gets_highest_confidence(db):
    db.add(
        UserCorrelation(
            user_id=USER,
            source_metric="protein_intake",
            target_metric="deep_sleep_seconds",
            lag_days=0,
            direction="positive",
            pearson_r=0.5,
            spearman_r=0.5,
            p_value=0.001,
            fdr_adjusted_p=0.01,
            sample_size=60,
            strength=0.5,
            confidence_tier="literature_supported",
            literature_match=True,
            literature_ref="10.1007/s40279-014-0260-0",
            effect_size_description="...",
        )
    )
    await db.flush()

    candidates = await cand_mod.generate_candidates(db, USER, TODAY)
    corr = candidates[0]
    assert corr.confidence == 0.95
    assert corr.literature_support is True
    assert corr.actionability_score == 1.0  # protein_intake is modifiable


# ─────────────────────────────────────────────────────────────────────────
# Anomaly -> candidate
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_anomaly_surfaces_as_candidate_with_z_effect_size(db):
    db.add(
        MLAnomaly(
            user_id=USER,
            metric_key="hrv",
            observation_date=(TODAY - timedelta(days=1)).isoformat(),
            observed_value=20.0,
            forecasted_value=40.0,
            residual=-20.0,
            z_score=-4.0,
            direction="low",
            confirmed_by_bocpd=True,
            model_version="residual-z-1.0.0",
        )
    )
    await db.flush()

    candidates = await cand_mod.generate_candidates(db, USER, TODAY)
    anoms = [c for c in candidates if c.kind == "anomaly"]
    assert len(anoms) == 1
    a = anoms[0]
    # |z| = 4.0 -> effect_size = 4/5 = 0.8
    assert a.effect_size == pytest.approx(0.8)
    # Confirmed by BOCPD -> higher confidence
    assert a.confidence == 0.80
    assert a.directional_support is True
    # HRV is a biometric, so actionability is lower.
    assert a.actionability_score == 0.4


@pytest.mark.asyncio
async def test_unconfirmed_anomaly_has_lower_confidence(db):
    db.add(
        MLAnomaly(
            user_id=USER,
            metric_key="hrv",
            observation_date=(TODAY - timedelta(days=1)).isoformat(),
            observed_value=20.0,
            forecasted_value=40.0,
            residual=-20.0,
            z_score=-3.5,
            direction="low",
            confirmed_by_bocpd=False,
            model_version="residual-z-1.0.0",
        )
    )
    await db.flush()

    candidates = await cand_mod.generate_candidates(db, USER, TODAY)
    a = [c for c in candidates if c.kind == "anomaly"][0]
    assert a.confidence == 0.60
    assert a.directional_support is False


@pytest.mark.asyncio
async def test_anomaly_outside_lookback_window_is_dropped(db):
    """Anomaly observed 10 days ago should NOT surface (default lookback 7)."""
    db.add(
        MLAnomaly(
            user_id=USER,
            metric_key="hrv",
            observation_date=(TODAY - timedelta(days=10)).isoformat(),
            observed_value=20.0,
            forecasted_value=40.0,
            residual=-20.0,
            z_score=-4.0,
            direction="low",
            confirmed_by_bocpd=True,
            model_version="residual-z-1.0.0",
        )
    )
    await db.flush()
    candidates = await cand_mod.generate_candidates(db, USER, TODAY)
    assert not any(c.kind == "anomaly" for c in candidates)


# ─────────────────────────────────────────────────────────────────────────
# Novelty
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_novelty_is_high_for_never_surfaced_candidate(db):
    """Brand-new candidate, never in ml_rankings -> novelty = 1.0."""
    db.add(
        UserCorrelation(
            user_id=USER,
            source_metric="steps",
            target_metric="sleep_efficiency",
            lag_days=0,
            direction="positive",
            pearson_r=0.7,
            spearman_r=0.7,
            p_value=0.01,
            fdr_adjusted_p=0.05,
            sample_size=35,
            strength=0.7,
            confidence_tier="developing",
            literature_match=False,
            effect_size_description="...",
        )
    )
    await db.flush()
    candidates = await cand_mod.generate_candidates(db, USER, TODAY)
    assert candidates[0].novelty == 1.0


@pytest.mark.asyncio
async def test_novelty_drops_after_recent_surface(db):
    """After the same candidate was shown (was_shown=True) in last 30 days,
    novelty should drop to 0.4."""
    db.add(
        UserCorrelation(
            user_id=USER,
            source_metric="steps",
            target_metric="sleep_efficiency",
            lag_days=0,
            direction="positive",
            pearson_r=0.7,
            spearman_r=0.7,
            p_value=0.01,
            fdr_adjusted_p=0.05,
            sample_size=35,
            strength=0.7,
            confidence_tier="developing",
            literature_match=False,
            effect_size_description="...",
        )
    )
    await db.flush()

    # Generate once to compute the expected candidate id.
    first_pass = await cand_mod.generate_candidates(db, USER, TODAY)
    candidate_id = first_pass[0].id

    # Simulate that it was surfaced three days ago.
    db.add(
        MLRanking(
            user_id=USER,
            surface_date=(TODAY - timedelta(days=3)).isoformat(),
            candidate_id=candidate_id,
            rank=1,
            score=0.8,
            ranker_version="heuristic-1.0.0",
            was_shown=True,
        )
    )
    await db.flush()

    second_pass = await cand_mod.generate_candidates(db, USER, TODAY)
    assert second_pass[0].novelty == 0.4


# ─────────────────────────────────────────────────────────────────────────
# Persistence
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_candidates_upserts_to_db(db):
    """Running generate_candidates persists each candidate; rerunning
    updates in place (no duplicates)."""
    db.add(
        UserCorrelation(
            user_id=USER,
            source_metric="steps",
            target_metric="sleep_efficiency",
            lag_days=0,
            direction="positive",
            pearson_r=0.7,
            spearman_r=0.7,
            p_value=0.01,
            fdr_adjusted_p=0.05,
            sample_size=35,
            strength=0.7,
            confidence_tier="developing",
            literature_match=False,
            effect_size_description="...",
        )
    )
    await db.flush()

    await cand_mod.generate_candidates(db, USER, TODAY)
    first = (await db.execute(select(MLInsightCandidate))).scalars().all()
    await cand_mod.generate_candidates(db, USER, TODAY)
    second = (await db.execute(select(MLInsightCandidate))).scalars().all()
    assert len(first) == len(second) == 1
    assert first[0].id == second[0].id


@pytest.mark.asyncio
async def test_persisted_candidate_carries_json_payload(db):
    """Payload dict should round-trip as JSON in payload_json."""
    db.add(
        UserCorrelation(
            user_id=USER,
            source_metric="steps",
            target_metric="sleep_efficiency",
            lag_days=0,
            direction="positive",
            pearson_r=0.7,
            spearman_r=0.7,
            p_value=0.01,
            fdr_adjusted_p=0.05,
            sample_size=35,
            strength=0.7,
            confidence_tier="developing",
            literature_match=False,
            effect_size_description="When your steps are higher, your sleep_efficiency tends to be higher too.",
        )
    )
    await db.flush()

    await cand_mod.generate_candidates(db, USER, TODAY)
    row = (await db.execute(select(MLInsightCandidate))).scalar_one()
    payload = json.loads(row.payload_json)
    assert payload["source_metric"] == "steps"
    assert payload["target_metric"] == "sleep_efficiency"
    assert payload["lag_days"] == 0
    assert payload["confidence_tier"] == "developing"
