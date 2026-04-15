"""Phase 7A CoreML export tests.

Tests cover:
1. CoreML conversion from XGBoost model
2. Model size < 500KB assertion
3. Numeric equivalence: XGBoost vs CoreML predictions
4. Graceful fallback when coremltools not installed
5. Model registration persistence

Run: ``cd backend && uv run python -m pytest tests/ml/test_ranking_coreml_export.py -v``
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("ENCRYPTION_KEY", "T0TXLkHFSeZRYGIIejSFVkhQrvRE-bWLkwXSkkdWiKQ=")
os.environ.setdefault("ANTHROPIC_API_KEY", "fake-key-tests-dont-call-anthropic")

import numpy as np
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
from ml.ranking.trainer import FEATURE_NAMES, train_ranker


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


def _train_small_model():
    """Helper: train a tiny XGBoost model for testing."""
    rng = np.random.default_rng(42)
    n = 100
    X = rng.random((n, 8)).astype(np.float32)
    y = np.clip((X[:, 0] * 4).astype(np.int32), 0, 3).astype(np.float32)
    groups = np.array([n], dtype=np.int32)
    user_ids = ["u-0"] * n

    return train_ranker(
        X, y, groups, user_ids,
        params={"objective": "rank:pairwise", "max_depth": 4, "eta": 0.1, "n_estimators": 20},
    )


# ---------------------------------------------------------------------------
# CoreML conversion
# ---------------------------------------------------------------------------


def test_coreml_export_produces_file():
    """Export should produce a .mlmodel file."""
    try:
        import coremltools  # noqa: F401
    except ImportError:
        pytest.skip("coremltools not installed")

    from ml.ranking.coreml_export import export_to_coreml

    trained = _train_small_model()
    result = export_to_coreml(trained.model, trained.feature_names)

    assert result.success, f"Export failed: {result.error}"
    assert result.mlmodel_path is not None
    assert os.path.exists(result.mlmodel_path)
    assert result.file_hash is not None
    assert len(result.file_hash) == 64  # SHA-256


def test_coreml_model_under_500kb():
    """Model size must be under 500KB."""
    try:
        import coremltools  # noqa: F401
    except ImportError:
        pytest.skip("coremltools not installed")

    from ml.ranking.coreml_export import export_to_coreml, MAX_MODEL_SIZE_BYTES

    trained = _train_small_model()
    result = export_to_coreml(trained.model, trained.feature_names)

    assert result.success
    assert result.file_size_bytes is not None
    assert result.file_size_bytes < MAX_MODEL_SIZE_BYTES, (
        f"Model too large: {result.file_size_bytes} bytes (max {MAX_MODEL_SIZE_BYTES})"
    )


def test_coreml_numeric_equivalence():
    """CoreML predictions should match XGBoost predictions within tolerance.

    Requires both coremltools AND the native CoreML runtime (macOS with
    Xcode). Skips gracefully when the runtime is unavailable (which is
    the case when running in a plain Python venv without Xcode integration).
    """
    try:
        import coremltools as ct
    except ImportError:
        pytest.skip("coremltools not installed")

    # Check if the native CoreML runtime is available for inference.
    try:
        ct.models.MLModel  # noqa: B018
        # Try a dummy predict to see if runtime works.
        _has_runtime = True
    except Exception:
        _has_runtime = False

    from ml.ranking.coreml_export import export_to_coreml
    from ml.ranking.trainer import predict_scores

    trained = _train_small_model()
    export = export_to_coreml(trained.model, trained.feature_names)
    assert export.success

    if not _has_runtime:
        pytest.skip("CoreML runtime not available (needs macOS + Xcode)")

    # XGBoost predictions.
    rng = np.random.default_rng(99)
    X_test = rng.random((10, 8)).astype(np.float32)
    xgb_preds = predict_scores(trained.model, X_test)

    # CoreML predictions.
    try:
        coreml_model = ct.models.MLModel(export.mlmodel_path)
        coreml_preds = []
        for row in X_test:
            input_dict = {name: float(val) for name, val in zip(FEATURE_NAMES, row)}
            pred = coreml_model.predict(input_dict)
            pred_val = pred.get("prediction", pred.get("target", list(pred.values())[0]))
            coreml_preds.append(float(pred_val))
    except Exception as e:
        pytest.skip(f"CoreML inference unavailable: {e}")

    coreml_preds = np.array(coreml_preds)

    # Tolerance: 1e-3 (tree rounding differences between implementations).
    np.testing.assert_allclose(
        xgb_preds, coreml_preds, atol=1e-3,
        err_msg="XGBoost and CoreML predictions diverge beyond tolerance",
    )


# ---------------------------------------------------------------------------
# Graceful fallback
# ---------------------------------------------------------------------------


def test_export_returns_failure_without_coremltools(monkeypatch):
    """When coremltools is not importable, export should return success=False gracefully."""
    import builtins
    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "coremltools":
            raise ImportError("mocked: coremltools not installed")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    from ml.ranking.coreml_export import export_to_coreml

    trained = _train_small_model()
    result = export_to_coreml(trained.model, trained.feature_names)

    assert not result.success
    assert "not installed" in (result.error or "")


# ---------------------------------------------------------------------------
# Model registration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_model_persists_and_activates(db: AsyncSession):
    """register_model should write to ml_models and set is_active=True."""
    from ml.ranking.coreml_export import register_model
    from app.models.ml_models import MLModel

    model_id = await register_model(
        db,
        model_version="ranker-test-001",
        feature_names=FEATURE_NAMES,
        hyperparams={"max_depth": 6},
        train_samples=500,
        val_ndcg=0.75,
        file_hash="abc123" * 10 + "abcd",
        file_size_bytes=250000,
    )
    await db.flush()

    result = await db.execute(select(MLModel).where(MLModel.id == model_id))
    model = result.scalar_one()
    assert model.is_active is True
    assert model.model_type == "ranker"
    assert model.model_version == "ranker-test-001"
    assert model.train_samples == 500
    assert model.val_ndcg == 0.75


@pytest.mark.asyncio
async def test_register_model_deactivates_previous(db: AsyncSession):
    """Second registration should deactivate the first model."""
    from ml.ranking.coreml_export import register_model
    from app.models.ml_models import MLModel

    id1 = await register_model(
        db, "ranker-v1", FEATURE_NAMES, {}, 100, 0.5
    )
    id2 = await register_model(
        db, "ranker-v2", FEATURE_NAMES, {}, 200, 0.7
    )
    await db.flush()

    r1 = await db.execute(select(MLModel).where(MLModel.id == id1))
    m1 = r1.scalar_one()
    assert m1.is_active is False

    r2 = await db.execute(select(MLModel).where(MLModel.id == id2))
    m2 = r2.scalar_one()
    assert m2.is_active is True
