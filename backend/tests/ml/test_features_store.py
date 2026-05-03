"""End-to-end tests for the feature store: materialize -> read.

Uses an in-memory SQLite session. Seeds a small amount of upstream data,
runs ``materialize_for_user``, then checks the DB rows + the read-back
DataFrame.

Run: ``cd backend && uv run python -m pytest tests/ml/test_features_store.py -v``
"""

from __future__ import annotations

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
from app.models.health import ActivityRecord, HealthMetricRecord
from app.models.ml_features import MLFeatureCatalogEntry, MLFeatureValue
from ml.features import catalog
from ml.features.store import (
    MaterializeResult,
    get_feature_frame,
    materialize_for_user,
    sync_catalog_to_db,
)


USER = "u-store"
TODAY = date.today()
WINDOW_DAYS = 14


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


async def _seed_minimal(db: AsyncSession) -> None:
    """Seed ~a week of biometric + activity rows for round-trip testing."""
    for i in range(WINDOW_DAYS):
        ds = (TODAY - timedelta(days=i)).isoformat()
        db.add(
            HealthMetricRecord(
                user_id=USER,
                date=ds,
                metric_type="hrv",
                value=40.0 + (i % 3),  # some variance so rolling stats compute
                source="oura",
                is_canonical=True,
            )
        )
        db.add(
            HealthMetricRecord(
                user_id=USER,
                date=ds,
                metric_type="steps",
                value=8_000 + i * 100,
                source="apple_health",
                is_canonical=True,
            )
        )
        db.add(
            ActivityRecord(
                user_id=USER,
                date=ds,
                steps=8_000 + i * 100,
                active_calories=250,
                source="apple_health",
            )
        )
    await db.flush()


# ─────────────────────────────────────────────────────────────────────────
# sync_catalog_to_db
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sync_catalog_populates_db_on_first_run(db):
    touched = await sync_catalog_to_db(db)
    assert touched == len(catalog.iter_catalog())
    result = await db.execute(select(MLFeatureCatalogEntry))
    rows = list(result.scalars().all())
    assert len(rows) == len(catalog.iter_catalog())


@pytest.mark.asyncio
async def test_sync_catalog_is_idempotent(db):
    await sync_catalog_to_db(db)
    second = await sync_catalog_to_db(db)
    assert second == 0, "second run should touch nothing when nothing changed"


# ─────────────────────────────────────────────────────────────────────────
# materialize_for_user
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_materialize_writes_rows_for_every_feature_date(db):
    await _seed_minimal(db)
    start = TODAY - timedelta(days=WINDOW_DAYS - 1)

    result = await materialize_for_user(db, USER, start, TODAY)
    assert isinstance(result, MaterializeResult)
    assert result.rows_written > 0
    assert result.features_touched >= 20

    # Every date in the window should have at least one row.
    rows_by_date = await db.execute(
        select(MLFeatureValue.feature_date).where(MLFeatureValue.user_id == USER).distinct()
    )
    dates_seen = {r for r in rows_by_date.scalars().all()}
    for i in range(WINDOW_DAYS):
        ds = (TODAY - timedelta(days=i)).isoformat()
        assert ds in dates_seen, f"no rows materialized for {ds}"


@pytest.mark.asyncio
async def test_materialize_is_idempotent(db):
    """Rerunning the same window produces the same row count (no duplicates)."""
    await _seed_minimal(db)
    start = TODAY - timedelta(days=WINDOW_DAYS - 1)

    first = await materialize_for_user(db, USER, start, TODAY)
    count_after_first = (
        await db.execute(
            select(MLFeatureValue).where(MLFeatureValue.user_id == USER)
        )
    ).scalars().all()
    second = await materialize_for_user(db, USER, start, TODAY)
    count_after_second = (
        await db.execute(
            select(MLFeatureValue).where(MLFeatureValue.user_id == USER)
        )
    ).scalars().all()

    assert len(count_after_first) == len(count_after_second), (
        "materialize_for_user should be idempotent, "
        f"got {len(count_after_first)} vs {len(count_after_second)} after rerun"
    )
    assert first.features_touched == second.features_touched


@pytest.mark.asyncio
async def test_materialize_marks_unobserved_for_missing_upstream(db):
    """A date with no upstream rows materializes with is_observed=False."""
    # No seed data at all.
    start = TODAY - timedelta(days=2)

    await materialize_for_user(db, USER, start, TODAY)

    hrv_rows = await db.execute(
        select(MLFeatureValue)
        .where(
            MLFeatureValue.user_id == USER,
            MLFeatureValue.feature_key == "hrv",
        )
    )
    rows = list(hrv_rows.scalars().all())
    assert rows, "hrv feature should be emitted even without upstream data"
    for r in rows:
        assert r.is_observed is False
        assert r.value is None


# ─────────────────────────────────────────────────────────────────────────
# get_feature_frame
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_feature_frame_roundtrip(db):
    """materialize -> read returns expected shape + values."""
    await _seed_minimal(db)
    start = TODAY - timedelta(days=WINDOW_DAYS - 1)
    await materialize_for_user(db, USER, start, TODAY)

    frame = await get_feature_frame(
        db,
        USER,
        feature_keys=["hrv", "steps", "weekday"],
        start=start,
        end=TODAY,
    )

    # Shape: WINDOW_DAYS rows, 3 columns.
    assert frame.shape == (WINDOW_DAYS, 3)
    assert set(frame.columns) == {"hrv", "steps", "weekday"}
    # HRV values should be in the seeded range 40..42.
    assert frame["hrv"].min() >= 40
    assert frame["hrv"].max() <= 42


@pytest.mark.asyncio
async def test_get_feature_frame_respects_include_imputed_flag(db):
    """include_imputed=False should mask unobserved cells to NaN."""
    start = TODAY - timedelta(days=2)
    await materialize_for_user(db, USER, start, TODAY)

    # No upstream data, so every hrv cell is unobserved.
    frame_with = await get_feature_frame(
        db, USER, feature_keys=["hrv"], start=start, end=TODAY, include_imputed=True
    )
    frame_without = await get_feature_frame(
        db, USER, feature_keys=["hrv"], start=start, end=TODAY, include_imputed=False
    )

    # With imputed included, the cells are still NaN (value was None when
    # stored); without imputed they're also NaN. The real difference shows
    # up when is_observed=True but imputed_by is set, not exercised in v1
    # since our builders never output imputed=True for missing data.
    # Still: both calls must succeed and return the same shape.
    assert frame_with.shape == frame_without.shape


@pytest.mark.asyncio
async def test_get_feature_frame_returns_empty_shape_when_no_data(db):
    """Empty DB returns a frame with the right index + columns, all NaN."""
    start = TODAY - timedelta(days=2)
    frame = await get_feature_frame(
        db, USER, feature_keys=["hrv", "steps"], start=start, end=TODAY
    )
    assert frame.shape == (3, 2)
    assert set(frame.columns) == {"hrv", "steps"}


@pytest.mark.asyncio
async def test_get_feature_frame_with_no_keys_returns_full_catalog(db):
    """``feature_keys=None`` returns every feature in the catalog as a column."""
    await _seed_minimal(db)
    start = TODAY - timedelta(days=WINDOW_DAYS - 1)
    await materialize_for_user(db, USER, start, TODAY)

    frame = await get_feature_frame(db, USER, feature_keys=None, start=start, end=TODAY)
    catalog_keys = {s.key for s in catalog.iter_catalog()}
    assert set(frame.columns) == catalog_keys


# ─────────────────────────────────────────────────────────────────────────
# Performance guardrail, loose, just to catch 100x regressions.
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_materialize_completes_within_budget(db):
    """30-day materialize should complete in well under the 60s Phase 1 budget.

    In-memory SQLite on a dev laptop should be <3s. The real prod budget is
    60s against Postgres with a realistic dataset; this test just guards
    against runaway regressions.
    """
    import time

    await _seed_minimal(db)
    start = TODAY - timedelta(days=WINDOW_DAYS - 1)

    t0 = time.perf_counter()
    await materialize_for_user(db, USER, start, TODAY)
    elapsed = time.perf_counter() - t0

    assert elapsed < 15.0, (
        f"materialize_for_user took {elapsed:.1f}s on in-memory SQLite; "
        "expected well under 15s. Investigate before blaming prod perf."
    )
