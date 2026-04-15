"""Phase 4.5 Commit 4: public-API wiring test.

``ml.api.generate_synth_cohort`` is the only import the rest of the
app is allowed to reach; the factory orchestrator lives behind it.
This test pins the delegation contract and that the public stub no
longer raises ``NotImplementedError``.

Run: ``cd backend && uv run python -m pytest tests/ml/test_synth_api.py -v``
"""

from __future__ import annotations

import os

os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-must-be-long-enough-for-hs256-aaaaaaaa")
os.environ.setdefault("ENCRYPTION_KEY", "T0TXLkHFSeZRYGIIejSFVkhQrvRE-bWLkwXSkkdWiKQ=")
os.environ.setdefault("ANTHROPIC_API_KEY", "fake-key-tests-dont-call-anthropic")

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models.health import HealthMetricRecord
from ml.api import CohortManifest, generate_synth_cohort


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


@pytest.mark.asyncio
async def test_public_entry_point_returns_cohort_manifest(db: AsyncSession) -> None:
    """Commit 1 left the stub raising NotImplementedError; Commit 4 must
    replace that with a working delegation to the factory."""
    manifest = await generate_synth_cohort(db, n_users=2, days=7, seed=42)
    assert isinstance(manifest, CohortManifest)
    assert manifest.n_users == 2
    assert manifest.days == 7
    assert manifest.generator == "parametric"


@pytest.mark.asyncio
async def test_public_entry_point_writes_rows(db: AsyncSession) -> None:
    await generate_synth_cohort(db, n_users=2, days=7, seed=42)
    await db.flush()
    metric_count = (
        await db.execute(select(func.count()).select_from(HealthMetricRecord))
    ).scalar_one()
    assert metric_count > 0


@pytest.mark.asyncio
async def test_defaults_fall_back_to_settings(db: AsyncSession) -> None:
    """Omitting ``days`` and ``generator`` must fall back to the
    MLSettings defaults rather than raising."""
    from ml.config import get_ml_settings

    settings = get_ml_settings()
    manifest = await generate_synth_cohort(db, n_users=1, seed=1)
    assert manifest.days == settings.synth_default_days
    assert manifest.generator == settings.synth_default_generator
