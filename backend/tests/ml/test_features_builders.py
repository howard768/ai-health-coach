"""Builder-level tests: each builder emits the right shape + values.

Uses an in-memory SQLite session with the full schema, seeds a small amount
of data per test, and checks the MaterializedValue rows each builder returns.

Derived builder is tested in-process (no DB) because it operates on a
pre-built DataFrame.

Run: ``cd backend && uv run python -m pytest tests/ml/test_features_builders.py -v``
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
from app.models.health import ActivityRecord, HealthMetricRecord, SleepRecord
from app.models.meal import FoodItemRecord, MealRecord
from ml.features import builders


USER = "u-test"
TODAY = date.today()
TODAY_S = TODAY.isoformat()
YESTERDAY = TODAY - timedelta(days=1)
YESTERDAY_S = YESTERDAY.isoformat()


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
# build_biometric_raw
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_biometric_raw_emits_one_row_per_feature_per_date(db):
    """Empty DB: every expected feature appears but all unobserved."""
    out = await builders.build_biometric_raw(db, USER, YESTERDAY, TODAY)
    # 7 biometric feature keys (hrv, resting_hr, sleep_efficiency,
    # sleep_duration_minutes, readiness_score, deep_sleep_minutes, rem_sleep_minutes)
    # x 2 dates = 14.
    assert len(out) == 14
    assert all(not mv.is_observed for mv in out)
    assert all(mv.value is None for mv in out)


@pytest.mark.asyncio
async def test_biometric_raw_reads_canonical_health_metric_records(db):
    """A canonical hrv row should surface as an observed hrv feature value."""
    db.add(
        HealthMetricRecord(
            user_id=USER,
            date=TODAY_S,
            metric_type="hrv",
            value=42.5,
            source="oura",
            is_canonical=True,
        )
    )
    # Also add a non-canonical competing row; should be ignored.
    db.add(
        HealthMetricRecord(
            user_id=USER,
            date=TODAY_S,
            metric_type="hrv",
            value=99.0,
            source="garmin",
            is_canonical=False,
        )
    )
    await db.flush()

    out = await builders.build_biometric_raw(db, USER, TODAY, TODAY)
    hrv_rows = [mv for mv in out if mv.feature_key == "hrv"]
    assert len(hrv_rows) == 1
    assert hrv_rows[0].is_observed
    assert hrv_rows[0].value == 42.5


@pytest.mark.asyncio
async def test_biometric_raw_converts_sleep_duration_seconds_to_minutes(db):
    db.add(
        HealthMetricRecord(
            user_id=USER,
            date=TODAY_S,
            metric_type="sleep_duration",
            value=28_800,  # 8 hours in seconds
            source="oura",
            is_canonical=True,
        )
    )
    await db.flush()

    out = await builders.build_biometric_raw(db, USER, TODAY, TODAY)
    dur = [mv for mv in out if mv.feature_key == "sleep_duration_minutes"]
    assert dur[0].value == pytest.approx(480.0)


@pytest.mark.asyncio
async def test_biometric_raw_falls_back_to_sleep_record_for_deep_rem(db):
    """deep_sleep_minutes / rem_sleep_minutes come from SleepRecord, not HealthMetricRecord."""
    db.add(
        SleepRecord(
            user_id=USER,
            date=TODAY_S,
            deep_sleep_seconds=3_600,  # 60 min
            rem_sleep_seconds=5_400,  # 90 min
        )
    )
    await db.flush()

    out = await builders.build_biometric_raw(db, USER, TODAY, TODAY)
    deep = next(mv for mv in out if mv.feature_key == "deep_sleep_minutes")
    rem = next(mv for mv in out if mv.feature_key == "rem_sleep_minutes")
    assert deep.is_observed and deep.value == pytest.approx(60.0)
    assert rem.is_observed and rem.value == pytest.approx(90.0)


# ─────────────────────────────────────────────────────────────────────────
# build_activity
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_activity_aggregates_steps_and_workouts(db):
    # Two workout rows on the same day, both with their own steps snapshot.
    # Activity builder takes max() of steps (daily aggregate is the largest
    # snapshot, not the sum across per-workout rows) and sums workout minutes.
    db.add_all(
        [
            ActivityRecord(
                user_id=USER,
                date=TODAY_S,
                steps=10_000,
                active_calories=300,
                workout_type="cycling",
                workout_duration_seconds=1_800,  # 30 min
                source="peloton",
            ),
            ActivityRecord(
                user_id=USER,
                date=TODAY_S,
                steps=10_500,  # slightly later snapshot
                active_calories=150,
                workout_type="running",
                workout_duration_seconds=900,  # 15 min
                source="garmin",
            ),
        ]
    )
    await db.flush()

    out = await builders.build_activity(db, USER, TODAY, TODAY)
    by_key = {mv.feature_key: mv for mv in out}
    assert by_key["steps"].value == 10_500
    assert by_key["active_calories"].value == 450  # sum of both
    assert by_key["workout_count"].value == 2
    assert by_key["workout_duration_sum_minutes"].value == pytest.approx(45.0)
    assert by_key["days_since_last_workout"].value == 0


@pytest.mark.asyncio
async def test_activity_days_since_last_workout_counts_back(db):
    three_days_ago = (TODAY - timedelta(days=3)).isoformat()
    db.add(
        ActivityRecord(
            user_id=USER,
            date=three_days_ago,
            workout_type="cycling",
            workout_duration_seconds=1_200,
            source="peloton",
        )
    )
    await db.flush()
    out = await builders.build_activity(db, USER, TODAY, TODAY)
    days_since = next(mv for mv in out if mv.feature_key == "days_since_last_workout")
    assert days_since.value == 3


# ─────────────────────────────────────────────────────────────────────────
# build_nutrition
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_nutrition_sums_food_item_macros(db):
    meal = MealRecord(user_id=USER, date=TODAY_S, meal_type="dinner", source="manual")
    db.add(meal)
    await db.flush()
    db.add_all(
        [
            FoodItemRecord(
                meal_id=meal.id,
                name="chicken breast",
                serving_size="6 oz",
                serving_count=2.0,
                calories=200,
                protein=30.0,
                carbs=0.0,
                fat=5.0,
                quality="whole",
                data_source="usda",
            ),
            FoodItemRecord(
                meal_id=meal.id,
                name="rice",
                serving_size="1 cup",
                serving_count=1.0,
                calories=400,
                protein=8.0,
                carbs=80.0,
                fat=2.0,
                quality="whole",
                data_source="usda",
            ),
        ]
    )
    await db.flush()

    out = await builders.build_nutrition(db, USER, TODAY, TODAY)
    by_key = {mv.feature_key: mv for mv in out}
    # 200 x 2 + 400 x 1 = 800
    assert by_key["calories"].value == pytest.approx(800.0)
    # 30 x 2 + 8 x 1 = 68
    assert by_key["protein_g"].value == pytest.approx(68.0)
    assert by_key["meal_count"].value == 1


@pytest.mark.asyncio
async def test_nutrition_empty_day_emits_unobserved(db):
    out = await builders.build_nutrition(db, USER, TODAY, TODAY)
    for mv in out:
        assert not mv.is_observed
        assert mv.value is None


# ─────────────────────────────────────────────────────────────────────────
# build_contextual
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_contextual_weekday_and_weekend(db):
    # 2026-04-14 is Tuesday (weekday=1). Also pick a Saturday for comparison.
    tue = date(2026, 4, 14)
    sat = date(2026, 4, 18)
    out = await builders.build_contextual(db, USER, tue, sat)
    by_date_key = {(mv.feature_date, mv.feature_key): mv for mv in out}
    assert by_date_key[(tue.isoformat(), "weekday")].value == 1
    assert by_date_key[(tue.isoformat(), "is_weekend")].value == 0
    assert by_date_key[(sat.isoformat(), "weekday")].value == 5
    assert by_date_key[(sat.isoformat(), "is_weekend")].value == 1


@pytest.mark.asyncio
async def test_contextual_days_since_install_needs_earliest_row(db):
    # No HealthMetricRecord yet: days_since_install is unobserved.
    out = await builders.build_contextual(db, USER, TODAY, TODAY)
    dsi = next(mv for mv in out if mv.feature_key == "days_since_install")
    assert not dsi.is_observed

    # Seed an earliest row 5 days back.
    five_ago = (TODAY - timedelta(days=5)).isoformat()
    db.add(
        HealthMetricRecord(
            user_id=USER,
            date=five_ago,
            metric_type="hrv",
            value=40.0,
            source="oura",
            is_canonical=True,
        )
    )
    await db.flush()
    out = await builders.build_contextual(db, USER, TODAY, TODAY)
    dsi = next(mv for mv in out if mv.feature_key == "days_since_install")
    assert dsi.is_observed
    assert dsi.value == 5


# ─────────────────────────────────────────────────────────────────────────
# build_quality (completeness masks)
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_quality_completeness_counts_observed_days(db):
    # 7 of the last 14 days have a canonical biometric row.
    for i in range(7):
        ds = (TODAY - timedelta(days=i)).isoformat()
        db.add(
            HealthMetricRecord(
                user_id=USER,
                date=ds,
                metric_type="hrv",
                value=40 + i,
                source="oura",
                is_canonical=True,
            )
        )
    await db.flush()

    out = await builders.build_quality(db, USER, TODAY, TODAY)
    biometric = next(mv for mv in out if mv.feature_key == "completeness_14d.biometric")
    assert biometric.is_observed
    assert biometric.value == pytest.approx(7 / 14)


# ─────────────────────────────────────────────────────────────────────────
# build_derived (pandas-only, no DB)
# ─────────────────────────────────────────────────────────────────────────


def test_derived_rolling_mean_and_delta():
    """Basic pandas sanity against a hand-built series."""
    import pandas as pd

    idx = [(date(2026, 4, 1) + timedelta(days=i)).isoformat() for i in range(10)]
    frame = pd.DataFrame({"hrv": list(range(40, 50))}, index=idx)

    out = builders.build_derived(
        frame,
        requested_keys={"hrv.7d_rolling_mean", "hrv.7d_delta"},
    )

    by_key = {(mv.feature_date, mv.feature_key): mv for mv in out}

    # rolling mean on day 0 has only 1 point (< min_periods=3) so NaN.
    assert not by_key[(idx[0], "hrv.7d_rolling_mean")].is_observed
    # By day 3 we have 4 points (>= min_periods), mean should be observed.
    assert by_key[(idx[3], "hrv.7d_rolling_mean")].is_observed

    # Delta is exactly 7 because series is 40,41,42,...
    # Day 7 delta = hrv[7] - hrv[0] = 47 - 40 = 7.
    delta = by_key[(idx[7], "hrv.7d_delta")]
    assert delta.is_observed
    assert delta.value == pytest.approx(7.0)


def test_derived_z_score_is_zero_for_constant_series():
    """Constant series -> z-score is undefined (std=0) -> NaN -> unobserved."""
    import pandas as pd

    idx = [(date(2026, 4, 1) + timedelta(days=i)).isoformat() for i in range(30)]
    frame = pd.DataFrame({"hrv": [42.0] * 30}, index=idx)

    out = builders.build_derived(frame, requested_keys={"hrv.z_score_28d"})
    # std=0 produces inf/NaN, which we classify as unobserved.
    for mv in out:
        assert not mv.is_observed
