"""Phase 4.5 Commit 3: ``is_synthetic`` column round-trips on every raw table.

Verifies the schema invariant that the Phase 4.5 synth factory will rely on:

- Every raw ingestion table has an ``is_synthetic`` boolean column.
- Default value is ``False`` for any ORM write that does not specify it
  (so existing real-ingestion code paths remain unaffected without edits).
- ``is_synthetic=True`` persists through a write + read round trip.
- Filtering by ``is_synthetic == False`` returns only real rows and
  ``is_synthetic == True`` returns only synth rows, so downstream callers
  (crisis evals, production aggregates, feature store builders) can rely
  on the tag to partition the two populations.

Design rationale is documented in
``~/.claude/plans/phase-4.5-scaffolding.md`` (option 1 in the is_synthetic
design decision, resolved 2026-04-14).

Run: ``cd backend && uv run python -m pytest tests/ml/test_is_synthetic_schema.py -v``
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio

os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-must-be-long-enough-for-hs256-aaaaaaaa")
os.environ.setdefault("ENCRYPTION_KEY", "T0TXLkHFSeZRYGIIejSFVkhQrvRE-bWLkwXSkkdWiKQ=")
os.environ.setdefault("ANTHROPIC_API_KEY", "fake-key-tests-dont-call-anthropic")

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models.health import ActivityRecord, HealthMetricRecord, SleepRecord
from app.models.meal import FoodItemRecord, MealRecord


USER = "u-synth-schema"
DAY = "2026-04-14"


@pytest_asyncio.fixture
async def db():
    """Fresh in-memory SQLite per test. Schema is built from SQLAlchemy
    metadata (``Base.metadata.create_all``) rather than running Alembic, which
    keeps the test fast and still exercises the model-level column definitions
    the migration has to stay in sync with.
    """
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
# Default-False invariant
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sleep_record_defaults_to_not_synthetic(db: AsyncSession) -> None:
    """A SleepRecord written without is_synthetic must land as is_synthetic=False."""
    db.add(SleepRecord(user_id=USER, date=DAY, efficiency=0.9, total_sleep_seconds=28_800))
    await db.flush()
    row = (await db.execute(select(SleepRecord))).scalar_one()
    assert row.is_synthetic is False


@pytest.mark.asyncio
async def test_health_metric_record_defaults_to_not_synthetic(db: AsyncSession) -> None:
    db.add(
        HealthMetricRecord(
            user_id=USER,
            date=DAY,
            metric_type="hrv",
            value=50.0,
            source="oura",
            is_canonical=True,
        )
    )
    await db.flush()
    row = (await db.execute(select(HealthMetricRecord))).scalar_one()
    assert row.is_synthetic is False


@pytest.mark.asyncio
async def test_activity_record_defaults_to_not_synthetic(db: AsyncSession) -> None:
    db.add(
        ActivityRecord(
            user_id=USER,
            date=DAY,
            steps=9_000,
            active_calories=300,
            source="apple_health",
        )
    )
    await db.flush()
    row = (await db.execute(select(ActivityRecord))).scalar_one()
    assert row.is_synthetic is False


@pytest.mark.asyncio
async def test_meal_record_defaults_to_not_synthetic(db: AsyncSession) -> None:
    db.add(
        MealRecord(
            user_id=USER,
            date=DAY,
            meal_type="dinner",
            source="text",
        )
    )
    await db.flush()
    row = (await db.execute(select(MealRecord))).scalar_one()
    assert row.is_synthetic is False


@pytest.mark.asyncio
async def test_food_item_record_defaults_to_not_synthetic(db: AsyncSession) -> None:
    meal = MealRecord(user_id=USER, date=DAY, meal_type="dinner", source="text")
    db.add(meal)
    await db.flush()
    db.add(
        FoodItemRecord(
            meal_id=meal.id,
            name="grilled salmon",
            serving_size="4 oz",
            serving_count=1.0,
            calories=230,
            protein=25.0,
            carbs=0.0,
            fat=14.0,
            quality="whole",
            data_source="usda",
        )
    )
    await db.flush()
    row = (await db.execute(select(FoodItemRecord))).scalar_one()
    assert row.is_synthetic is False


# ─────────────────────────────────────────────────────────────────────────
# Round-trip True
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_is_synthetic_true_round_trips_on_every_raw_table(
    db: AsyncSession,
) -> None:
    """Setting is_synthetic=True at write time must persist unchanged across
    all five raw tables. This is the write path the synth factory (Commit 4)
    will exercise on every row it generates.
    """
    db.add(
        SleepRecord(
            user_id=USER,
            date=DAY,
            efficiency=0.9,
            total_sleep_seconds=28_800,
            is_synthetic=True,
        )
    )
    db.add(
        HealthMetricRecord(
            user_id=USER,
            date=DAY,
            metric_type="hrv",
            value=50.0,
            source="synth",
            is_canonical=False,
            is_synthetic=True,
        )
    )
    db.add(
        ActivityRecord(
            user_id=USER,
            date=DAY,
            steps=9_000,
            active_calories=300,
            source="synth",
            is_synthetic=True,
        )
    )
    meal = MealRecord(
        user_id=USER,
        date=DAY,
        meal_type="dinner",
        source="synth",
        is_synthetic=True,
    )
    db.add(meal)
    await db.flush()
    db.add(
        FoodItemRecord(
            meal_id=meal.id,
            name="synthetic salmon",
            serving_size="4 oz",
            serving_count=1.0,
            calories=230,
            protein=25.0,
            carbs=0.0,
            fat=14.0,
            quality="whole",
            data_source="ai_estimate",
            is_synthetic=True,
        )
    )
    await db.flush()

    for model in (SleepRecord, HealthMetricRecord, ActivityRecord, MealRecord, FoodItemRecord):
        row = (await db.execute(select(model))).scalar_one()
        assert row.is_synthetic is True, f"{model.__name__} lost is_synthetic=True on round trip"


# ─────────────────────────────────────────────────────────────────────────
# Partition invariant (filter semantics the downstream code relies on)
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_filter_partitions_real_and_synth_rows_cleanly(
    db: AsyncSession,
) -> None:
    """Given a mixed population, ``WHERE is_synthetic = False`` must return only
    real rows and ``WHERE is_synthetic = True`` must return only synth rows.

    Crisis evals and production aggregates (Phase 4.5 invariant #9) rely on
    this to unconditionally filter out synth data; this test pins that
    contract at the schema layer before Commit 4 starts writing mixed rows.
    """
    # Two real rows and two synth rows, same user, same date.
    db.add(HealthMetricRecord(
        user_id=USER, date=DAY, metric_type="hrv",
        value=50.0, source="oura", is_canonical=True,
    ))
    db.add(HealthMetricRecord(
        user_id=USER, date=DAY, metric_type="steps",
        value=9_000.0, source="apple_health", is_canonical=True,
    ))
    db.add(HealthMetricRecord(
        user_id=USER, date=DAY, metric_type="hrv",
        value=42.0, source="synth", is_canonical=False, is_synthetic=True,
    ))
    db.add(HealthMetricRecord(
        user_id=USER, date=DAY, metric_type="steps",
        value=8_500.0, source="synth", is_canonical=False, is_synthetic=True,
    ))
    await db.flush()

    real_rows = (
        await db.execute(
            select(HealthMetricRecord).where(HealthMetricRecord.is_synthetic.is_(False))
        )
    ).scalars().all()
    synth_rows = (
        await db.execute(
            select(HealthMetricRecord).where(HealthMetricRecord.is_synthetic.is_(True))
        )
    ).scalars().all()

    assert len(real_rows) == 2
    assert len(synth_rows) == 2
    assert all(r.source != "synth" for r in real_rows)
    assert all(r.source == "synth" for r in synth_rows)
