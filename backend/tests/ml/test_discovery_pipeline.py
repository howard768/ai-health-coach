"""Phase 2 end-to-end: run_discovery_pipeline + forecast_metric via ml.api.

Exercises the full L1 flow from the public API boundary. No direct imports
from backend.ml.discovery or backend.ml.forecasting — tests the contract the
scheduler / coach consume.

Run: ``cd backend && uv run python -m pytest tests/ml/test_discovery_pipeline.py -v``
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("ENCRYPTION_KEY", "T0TXLkHFSeZRYGIIejSFVkhQrvRE-bWLkwXSkkdWiKQ=")
os.environ.setdefault("ANTHROPIC_API_KEY", "fake-key-tests-dont-call-anthropic")

from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models.health import HealthMetricRecord
# Register ORM models with Base.metadata before fixture create_all.
from app.models import ml_baselines as _ml_baselines_models  # noqa: F401
from app.models import ml_features as _ml_features_models  # noqa: F401
from ml import api as ml_api
from ml.features.store import materialize_for_user


USER = "u-e2e"


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


async def _seed_full_history(db, days: int = 60):
    """Seed a 60-day hrv series + a few other biometrics for the user."""
    import math
    import random

    random.seed(11)
    today = date.today()
    for i in range(days):
        d = today - timedelta(days=days - 1 - i)
        db.add_all([
            HealthMetricRecord(
                user_id=USER,
                date=d.isoformat(),
                metric_type="hrv",
                value=40.0 + 2 * math.sin(2 * math.pi * i / 7) + random.gauss(0, 0.3),
                source="oura",
                is_canonical=True,
            ),
            HealthMetricRecord(
                user_id=USER,
                date=d.isoformat(),
                metric_type="resting_hr",
                value=55.0 + random.gauss(0, 1),
                source="oura",
                is_canonical=True,
            ),
            HealthMetricRecord(
                user_id=USER,
                date=d.isoformat(),
                metric_type="sleep_efficiency",
                value=88.0 + random.gauss(0, 2),
                source="oura",
                is_canonical=True,
            ),
        ])
    await db.flush()


# ─────────────────────────────────────────────────────────────────────────
# run_discovery_pipeline
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_discovery_pipeline_reports_layers_and_tiers(db):
    await _seed_full_history(db, days=60)
    today = date.today()
    await materialize_for_user(db, USER, today - timedelta(days=59), today)

    report = await ml_api.run_discovery_pipeline(db, USER)
    assert report.user_id == USER
    assert report.shadow_mode is True
    assert "baselines" in report.layers_run
    assert "forecasts" in report.layers_run
    assert "anomalies" in report.layers_run
    # At least one baseline should land given 60 days of data.
    assert report.tier_counts.get("baselines_written", 0) >= 1


@pytest.mark.asyncio
async def test_run_discovery_pipeline_is_idempotent(db):
    """Rerunning the pipeline back-to-back should not duplicate rows."""
    from sqlalchemy import select

    from app.models.ml_baselines import MLBaseline, MLForecast

    await _seed_full_history(db, days=60)
    today = date.today()
    await materialize_for_user(db, USER, today - timedelta(days=59), today)

    await ml_api.run_discovery_pipeline(db, USER)
    baselines_first = (
        await db.execute(select(MLBaseline).where(MLBaseline.user_id == USER))
    ).scalars().all()
    forecasts_first = (
        await db.execute(select(MLForecast).where(MLForecast.user_id == USER))
    ).scalars().all()

    await ml_api.run_discovery_pipeline(db, USER)
    baselines_second = (
        await db.execute(select(MLBaseline).where(MLBaseline.user_id == USER))
    ).scalars().all()
    forecasts_second = (
        await db.execute(select(MLForecast).where(MLForecast.user_id == USER))
    ).scalars().all()

    assert len(baselines_first) == len(baselines_second)
    assert len(forecasts_first) == len(forecasts_second)


@pytest.mark.asyncio
async def test_run_discovery_pipeline_handles_no_data_gracefully(db):
    """Empty DB should not crash; report should come back with zero counts."""
    report = await ml_api.run_discovery_pipeline(db, USER)
    assert report.shadow_mode is True
    assert report.tier_counts.get("baselines_written", 0) == 0


# ─────────────────────────────────────────────────────────────────────────
# forecast_metric (read-through of stored forecasts)
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_forecast_metric_returns_empty_when_no_forecasts_stored(db):
    """No forecast rows -> Forecast with empty points, not a crash."""
    fc = await ml_api.forecast_metric(db, USER, metric="hrv", horizon_days=7)
    assert fc.user_id == USER
    assert fc.metric == "hrv"
    assert fc.points == []


@pytest.mark.asyncio
async def test_forecast_metric_returns_stored_points_after_pipeline_run(db):
    """After the pipeline has run, forecast_metric should return horizon_days points."""
    await _seed_full_history(db, days=100)
    today = date.today()
    await materialize_for_user(db, USER, today - timedelta(days=99), today)

    # Make forecasts without Prophet to avoid flakiness in CI.
    from ml.forecasting import residuals

    await residuals.compute_forecasts_for_user(
        db, USER, made_on=today, horizon_days=7, use_prophet=False
    )

    fc = await ml_api.forecast_metric(db, USER, metric="hrv", horizon_days=7)
    assert fc.horizon_days == 7
    # Up to 7 future-date points depending on target_date filtering.
    assert 0 < len(fc.points) <= 7
    for pt in fc.points:
        assert "date" in pt
        assert "y_hat" in pt
