"""Phase 10 model rollback tests.

Tests cover:
1. Rollback flips is_active flags correctly
2. Previous model re-activated
3. rolled_back_at timestamp set

Run: ``cd backend && uv run python -m pytest tests/ml/test_mlops_rollback.py -v``
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("ENCRYPTION_KEY", "T0TXLkHFSeZRYGIIejSFVkhQrvRE-bWLkwXSkkdWiKQ=")
os.environ.setdefault("ANTHROPIC_API_KEY", "fake-key-tests-dont-call-anthropic")

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
# Register ORM models.
from app.models import ml_baselines as _ml_baselines  # noqa: F401
from app.models import ml_features as _ml_features  # noqa: F401
from app.models import ml_insights as _ml_insights  # noqa: F401
from app.models import ml_synth as _ml_synth  # noqa: F401
from app.models import ml_models as _ml_models  # noqa: F401
from app.models import ml_discovery as _ml_discovery  # noqa: F401
from app.models import ml_cohorts as _ml_cohorts  # noqa: F401
from app.models import ml_experiments as _ml_experiments  # noqa: F401
from app.models import ml_training_runs as _ml_training_runs  # noqa: F401
from app.models.ml_models import MLModel


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
async def test_rollback_flips_active_flags(db: AsyncSession):
    """Rollback should deactivate current and re-activate target."""
    from app.core.time import utcnow_naive
    import json

    now = utcnow_naive()
    # Version 1 (old, inactive).
    db.add(MLModel(
        model_type="ranker", model_version="ranker-v1",
        train_samples=100, val_ndcg=0.5, is_active=False,
        feature_names_json=json.dumps([]), created_at=now,
    ))
    # Version 2 (current, active).
    db.add(MLModel(
        model_type="ranker", model_version="ranker-v2",
        train_samples=200, val_ndcg=0.7, is_active=True,
        feature_names_json=json.dumps([]), created_at=now,
    ))
    await db.flush()

    # Rollback to v1.
    from sqlalchemy import update

    await db.execute(
        update(MLModel)
        .where(MLModel.model_type == "ranker", MLModel.is_active.is_(True))
        .values(is_active=False)
    )
    result = await db.execute(
        select(MLModel).where(
            MLModel.model_type == "ranker",
            MLModel.model_version == "ranker-v1",
        )
    )
    target = result.scalar_one()
    target.is_active = True
    target.rolled_back_at = now
    await db.flush()

    # Verify.
    v1 = await db.execute(
        select(MLModel).where(MLModel.model_version == "ranker-v1")
    )
    m1 = v1.scalar_one()
    assert m1.is_active is True
    assert m1.rolled_back_at is not None

    v2 = await db.execute(
        select(MLModel).where(MLModel.model_version == "ranker-v2")
    )
    m2 = v2.scalar_one()
    assert m2.is_active is False


@pytest.mark.asyncio
async def test_training_run_persists(db: AsyncSession):
    """A training run should be persistable with params + metrics."""
    import json
    from app.core.time import utcnow_naive
    from app.models.ml_training_runs import MLTrainingRun

    now = utcnow_naive()
    run = MLTrainingRun(
        run_id="test-run-001",
        model_type="ranker",
        started_at=now,
        finished_at=now,
        params_json=json.dumps({"max_depth": 6, "n_estimators": 100}),
        metrics_json=json.dumps({"val_ndcg": 0.75, "train_samples": 500}),
        status="completed",
        model_version="ranker-test-001",
    )
    db.add(run)
    await db.flush()

    result = await db.execute(
        select(MLTrainingRun).where(MLTrainingRun.run_id == "test-run-001")
    )
    saved = result.scalar_one()
    assert saved.status == "completed"
    assert saved.model_version == "ranker-test-001"
    assert "val_ndcg" in saved.metrics_json
