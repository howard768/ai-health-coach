"""Tests for the unified health data loader (health_data.py).

This is the single source of truth for all health data in the app.
Every coach data bug (deep sleep=0, wrong source attribution, stale metrics)
traces back to this module. These tests prevent the entire class of
"coach said 0 deep sleep" issues.

Run: cd backend && uv run python -m pytest tests/test_health_data.py -v
"""

import os
import pytest
import pytest_asyncio

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("ENCRYPTION_KEY", "T0TXLkHFSeZRYGIIejSFVkhQrvRE-bWLkwXSkkdWiKQ=")
os.environ.setdefault("ANTHROPIC_API_KEY", "fake-key-tests-dont-call-anthropic")

from datetime import date, timedelta

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.database import Base
from app.models.health import HealthMetricRecord, SleepRecord
from app.services.health_data import get_latest_health_data, get_health_data_range


# ── Fixtures ────────────────────────────────────────────────

TODAY = date.today().isoformat()
YESTERDAY = (date.today() - timedelta(days=1)).isoformat()


@pytest_asyncio.fixture
async def db():
    """In-memory async SQLite session with all tables created."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def _seed_reconciled(db: AsyncSession, user_id: str, target_date: str, metrics: dict, source: str = "oura"):
    """Seed canonical HealthMetricRecord rows for a date."""
    for metric_type, value in metrics.items():
        db.add(HealthMetricRecord(
            user_id=user_id, date=target_date,
            metric_type=metric_type, value=value,
            source=source, is_canonical=True,
        ))
    await db.flush()


async def _seed_sleep_record(db: AsyncSession, user_id: str, target_date: str, **kwargs):
    """Seed a SleepRecord row."""
    db.add(SleepRecord(
        user_id=user_id, date=target_date,
        efficiency=kwargs.get("efficiency"),
        total_sleep_seconds=kwargs.get("total_sleep_seconds"),
        deep_sleep_seconds=kwargs.get("deep_sleep_seconds"),
        hrv_average=kwargs.get("hrv_average"),
        resting_hr=kwargs.get("resting_hr"),
        readiness_score=kwargs.get("readiness_score"),
    ))
    await db.flush()


# ── Core Behavior ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_returns_reconciled_over_sleep_record(db):
    """When HealthMetricRecord exists, SleepRecord fallback is NOT used."""
    await _seed_reconciled(db, "u1", YESTERDAY, {"sleep_efficiency": 77, "hrv": 38})
    # Also seed a SleepRecord with different values
    await _seed_sleep_record(db, "u1", YESTERDAY, efficiency=60, hrv_average=25)
    await db.commit()

    result = await get_latest_health_data(db, "u1")
    assert result["sleep_efficiency"] == 77  # From reconciled, not SleepRecord
    assert result["hrv_average"] == 38


@pytest.mark.asyncio
async def test_yesterday_sleep_carries_forward(db):
    """Sleep metrics from yesterday fill in when today only has steps."""
    await _seed_reconciled(db, "u1", YESTERDAY, {
        "sleep_efficiency": 77, "hrv": 38, "resting_hr": 57, "readiness": 65,
    })
    await _seed_reconciled(db, "u1", TODAY, {"steps": 4201}, source="apple_health")
    await db.commit()

    result = await get_latest_health_data(db, "u1")
    assert result["sleep_efficiency"] == 77
    assert result["hrv_average"] == 38
    assert result["steps"] == 4201


@pytest.mark.asyncio
async def test_today_steps_overlay_yesterday(db):
    """Today's steps overwrite yesterday's."""
    await _seed_reconciled(db, "u1", YESTERDAY, {"steps": 100}, source="apple_health")
    await _seed_reconciled(db, "u1", TODAY, {"steps": 4201}, source="apple_health")
    await db.commit()

    result = await get_latest_health_data(db, "u1")
    assert result["steps"] == 4201


@pytest.mark.asyncio
async def test_deep_sleep_from_sleep_record(db):
    """Deep sleep minutes are pulled from SleepRecord even in reconciled path."""
    await _seed_reconciled(db, "u1", YESTERDAY, {"sleep_efficiency": 77})
    await _seed_sleep_record(db, "u1", YESTERDAY, deep_sleep_seconds=2880)  # 48 min
    await db.commit()

    result = await get_latest_health_data(db, "u1")
    assert result["deep_sleep_minutes"] == 48


@pytest.mark.asyncio
async def test_source_attribution_preserved(db):
    """data_sources dict shows correct source per metric."""
    await _seed_reconciled(db, "u1", YESTERDAY, {"sleep_efficiency": 77}, source="oura")
    await _seed_reconciled(db, "u1", TODAY, {"steps": 4201}, source="apple_health")
    await db.commit()

    result = await get_latest_health_data(db, "u1")
    sources = result["data_sources"]
    assert sources["steps"] == "apple_health"
    assert sources["sleep_efficiency"] == "oura"


@pytest.mark.asyncio
async def test_baselines_7day_average(db):
    """baseline_hrv and baseline_rhr are 7-day rolling averages."""
    # Seed 7 days of HRV data: 30, 32, 34, 36, 38, 40, 42 → avg = 36
    for i in range(7):
        day = (date.today() - timedelta(days=i)).isoformat()
        await _seed_reconciled(db, "u1", day, {"hrv": 30 + i * 2})
    # Need at least yesterday's sleep data to trigger reconciled path
    await _seed_reconciled(db, "u1", YESTERDAY, {"sleep_efficiency": 80})
    await db.commit()

    result = await get_latest_health_data(db, "u1")
    # 7-day average of [30, 32, 34, 36, 38, 40, 42] = 36.0
    assert result["baseline_hrv"] == 36.0


@pytest.mark.asyncio
async def test_empty_user_returns_empty_dict(db):
    """New user with no data returns {}."""
    result = await get_latest_health_data(db, "no-such-user")
    assert result == {}


@pytest.mark.asyncio
async def test_fallback_to_sleep_record(db):
    """When no HealthMetricRecord exists, SleepRecord data is returned."""
    await _seed_sleep_record(db, "u1", YESTERDAY,
                             efficiency=82, total_sleep_seconds=25200,
                             deep_sleep_seconds=3600, hrv_average=45,
                             resting_hr=60, readiness_score=75)
    await db.commit()

    result = await get_latest_health_data(db, "u1")
    assert result["sleep_efficiency"] == 82
    assert result["deep_sleep_minutes"] == 60
    assert result["hrv_average"] == 45


@pytest.mark.asyncio
async def test_zero_values_not_dropped(db):
    """HRV=0, steps=0 are returned as 0, not omitted."""
    await _seed_reconciled(db, "u1", YESTERDAY, {"hrv": 0, "sleep_efficiency": 0})
    await _seed_reconciled(db, "u1", TODAY, {"steps": 0}, source="apple_health")
    await db.commit()

    result = await get_latest_health_data(db, "u1")
    assert result["hrv_average"] == 0
    assert result["steps"] == 0
    assert result["sleep_efficiency"] == 0


# ── Date Range (Trends) ────────────────────────────────────


@pytest.mark.asyncio
async def test_health_data_range_returns_correct_days(db):
    """get_health_data_range returns data for the requested window."""
    for i in range(10):
        day = (date.today() - timedelta(days=i)).isoformat()
        await _seed_reconciled(db, "u1", day, {"hrv": 30 + i})
    await db.commit()

    result = await get_health_data_range(db, "u1", days=7)
    assert len(result) == 7  # Exactly 7 days (today through 6 days ago)
    # All dates should be within the last 7 days
    cutoff = (date.today() - timedelta(days=6)).isoformat()
    for item in result:
        assert item["date"] >= cutoff
