"""Tests for the SHAP-style explainer.

Correlation kind is pure Python. Anomaly kind is DB-seeded: feature store
must be materialized so the baseline-delta heuristic has data to rank.

Full XGBoost + shap.TreeExplainer is a Phase 5.1 follow-up; this suite
pins the Phase 5 heuristic contract.

Run: ``cd backend && uv run python -m pytest tests/ml/test_narrate_shap_explainer.py -v``
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

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models.health import ActivityRecord, HealthMetricRecord
# Register ORM models before create_all.
from app.models import ml_baselines as _ml_baselines_models  # noqa: F401
from app.models import ml_features as _ml_features_models  # noqa: F401
from app.models import ml_insights as _ml_insights_models  # noqa: F401
from app.models.ml_insights import MLInsightCandidate
from ml.features.store import materialize_for_user
from ml.narrate import shap_explainer


USER = "u-shap"
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
# Correlation path (no DB fetch needed beyond the candidate row)
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_correlation_returns_source_target_contributions(db):
    # Seed a candidate directly so explain() can look it up.
    payload = {
        "source_metric": "protein_intake",
        "target_metric": "deep_sleep_seconds",
        "direction": "positive",
        "pearson_r": 0.55,
        "spearman_r": 0.52,
        "sample_size": 60,
        "confidence_tier": "literature_supported",
        "literature_ref": "10.1007/s40279-014-0260-0",
    }
    db.add(
        MLInsightCandidate(
            id="cand-corr-1",
            user_id=USER,
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
            payload_json=json.dumps(payload),
        )
    )
    await db.flush()

    result = await shap_explainer.explain(db, USER, "cand-corr-1")
    assert result is not None
    assert result.kind == "correlation"
    # Source + target + dual-method agreement should appear in contributions.
    feature_names = [c.feature for c in result.contributions]
    assert any("protein_intake" in f for f in feature_names)
    assert any("deep_sleep_seconds" in f for f in feature_names)
    # Historical examples include sample size + literature reference.
    kinds = [h["kind"] for h in result.historical_examples]
    assert "sample_size" in kinds
    assert "literature" in kinds


@pytest.mark.asyncio
async def test_explain_returns_none_for_missing_candidate(db):
    assert await shap_explainer.explain(db, USER, "does-not-exist") is None


@pytest.mark.asyncio
async def test_explain_rejects_other_users_candidate(db):
    # Seed a candidate owned by someone else.
    db.add(
        MLInsightCandidate(
            id="cand-other",
            user_id="someone-else",
            kind="correlation",
            subject_metrics_json=json.dumps(["x"]),
            effect_size=0.5,
            confidence=0.6,
            novelty=1.0,
            recency_days=0,
            actionability_score=0.5,
            literature_support=False,
            directional_support=False,
            causal_support=False,
            payload_json=json.dumps({}),
        )
    )
    await db.flush()

    assert await shap_explainer.explain(db, USER, "cand-other") is None


# ─────────────────────────────────────────────────────────────────────────
# Anomaly path, DB-seeded
# ─────────────────────────────────────────────────────────────────────────


async def _seed_anomaly_context(db, user_id: str, days: int = 35):
    """Seed 35 days of steady biometrics; then on the anomaly date (today),
    spike steps way down so it ranks as a driver.

    Steps is sourced from ActivityRecord (not HealthMetricRecord) per the
    feature builder's source mapping, so we seed ActivityRecord directly.
    """
    import random

    random.seed(3)

    for i in range(days):
        d = TODAY - timedelta(days=days - 1 - i)

        steps_base = 10_000 if i < days - 1 else 1_500  # drop on the last day
        steps_value = int(max(0, steps_base + random.gauss(0, 100)))
        db.add_all([
            HealthMetricRecord(
                user_id=user_id,
                date=d.isoformat(),
                metric_type="hrv",
                value=40.0 + random.gauss(0, 1),
                source="oura",
                is_canonical=True,
            ),
            HealthMetricRecord(
                user_id=user_id,
                date=d.isoformat(),
                metric_type="resting_hr",
                value=55.0 + random.gauss(0, 0.5),
                source="oura",
                is_canonical=True,
            ),
            ActivityRecord(
                user_id=user_id,
                date=d.isoformat(),
                steps=steps_value,
                active_calories=250,
                source="apple_health",
            ),
        ])
    await db.flush()


@pytest.mark.asyncio
async def test_anomaly_ranks_features_by_baseline_deviation(db):
    await _seed_anomaly_context(db, USER, days=35)
    await materialize_for_user(db, USER, TODAY - timedelta(days=34), TODAY)

    payload = {
        "metric_key": "hrv",  # the "anomaly" metric itself
        "observation_date": TODAY.isoformat(),
        "direction": "low",
        "z_score": -3.5,
        "observed_value": 25.0,
        "forecasted_value": 40.0,
        "confirmed_by_bocpd": True,
    }
    db.add(
        MLInsightCandidate(
            id="cand-anom-1",
            user_id=USER,
            kind="anomaly",
            subject_metrics_json=json.dumps(["hrv"]),
            effect_size=0.7,
            confidence=0.8,
            novelty=1.0,
            recency_days=0,
            actionability_score=0.4,
            literature_support=False,
            directional_support=True,
            causal_support=False,
            payload_json=json.dumps(payload),
        )
    )
    await db.flush()

    result = await shap_explainer.explain(db, USER, "cand-anom-1")
    assert result is not None
    assert result.kind == "anomaly"
    # Steps was spiked down on TODAY, should rank highest by |z-score|.
    feature_names = [c.feature for c in result.contributions]
    assert "steps" in feature_names
    # The metric_key itself (hrv) is deliberately excluded.
    assert "hrv" not in feature_names
    # Confirmed-by-BOCPD flag flows into historical_examples.
    kinds = [h["kind"] for h in result.historical_examples]
    assert "two_signal_confirmation" in kinds


@pytest.mark.asyncio
async def test_anomaly_with_missing_observation_date_returns_empty_contributions(db):
    db.add(
        MLInsightCandidate(
            id="cand-anom-nodate",
            user_id=USER,
            kind="anomaly",
            subject_metrics_json=json.dumps(["hrv"]),
            effect_size=0.5,
            confidence=0.6,
            novelty=1.0,
            recency_days=0,
            actionability_score=0.4,
            literature_support=False,
            directional_support=False,
            causal_support=False,
            payload_json=json.dumps({"metric_key": "hrv"}),  # no observation_date
        )
    )
    await db.flush()

    result = await shap_explainer.explain(db, USER, "cand-anom-nodate")
    assert result is not None
    # Graceful degradation: empty contributions, no crash.
    assert result.contributions == []


@pytest.mark.asyncio
async def test_unknown_kind_returns_empty_explanation(db):
    db.add(
        MLInsightCandidate(
            id="cand-unk",
            user_id=USER,
            kind="brand_new_kind",
            subject_metrics_json=json.dumps(["mystery"]),
            effect_size=0.5,
            confidence=0.6,
            novelty=1.0,
            recency_days=0,
            actionability_score=0.5,
            literature_support=False,
            directional_support=False,
            causal_support=False,
            payload_json=json.dumps({}),
        )
    )
    await db.flush()

    result = await shap_explainer.explain(db, USER, "cand-unk")
    assert result is not None
    assert result.kind == "brand_new_kind"
    assert result.contributions == []
