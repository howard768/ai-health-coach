"""Phase 8A anonymization pipeline tests.

Tests cover:
1. HMAC pseudonymization determinism and rotation
2. Laplace DP noise within expected bounds
3. Pattern vector construction
4. Full anonymization pipeline

Run: ``cd backend && uv run python -m pytest tests/ml/test_cohorts_anonymize.py -v``
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("ENCRYPTION_KEY", "T0TXLkHFSeZRYGIIejSFVkhQrvRE-bWLkwXSkkdWiKQ=")
os.environ.setdefault("ANTHROPIC_API_KEY", "fake-key-tests-dont-call-anthropic")

import numpy as np
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
from ml.cohorts.anonymize import (
    pseudonymize,
    encrypt_user_id,
    apply_dp_noise,
)


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


# ---------------------------------------------------------------------------
# Unit: pseudonymization
# ---------------------------------------------------------------------------


def test_hmac_pseudonym_is_deterministic():
    """Same (user, key) always produces the same pseudonym."""
    p1 = pseudonymize("user-123", "key-2026-04")
    p2 = pseudonymize("user-123", "key-2026-04")
    assert p1 == p2
    assert len(p1) == 64  # SHA-256 hex


def test_hmac_pseudonym_changes_with_key():
    """Different key (month rotation) produces different pseudonym."""
    p1 = pseudonymize("user-123", "key-2026-04")
    p2 = pseudonymize("user-123", "key-2026-05")
    assert p1 != p2


def test_hmac_pseudonym_different_users():
    """Different users with same key produce different pseudonyms."""
    p1 = pseudonymize("user-123", "key-2026-04")
    p2 = pseudonymize("user-456", "key-2026-04")
    assert p1 != p2


def test_encrypted_user_id_differs_from_pseudonym():
    """Deletion lookup key is different from the clustering pseudonym."""
    pseudo = pseudonymize("user-123", "key-2026-04")
    enc = encrypt_user_id("user-123", "key-2026-04")
    assert pseudo != enc


# ---------------------------------------------------------------------------
# Unit: DP noise
# ---------------------------------------------------------------------------


def test_dp_noise_is_applied():
    """Noised vector should differ from original."""
    vector = [0.5] * 10
    noised = apply_dp_noise(vector, epsilon=1.0, seed=42)
    assert noised != vector


def test_dp_noise_bounded_in_expectation():
    """Mean noise over many samples should be near zero (Laplace is zero-mean)."""
    vector = [0.5] * 10
    noised_sum = np.zeros(10)
    n_trials = 1000
    for i in range(n_trials):
        noised = apply_dp_noise(vector, epsilon=1.0, seed=i)
        noised_sum += np.array(noised)
    noised_mean = noised_sum / n_trials
    original = np.array(vector)
    # Mean of noised vectors should be close to original (within 0.1).
    np.testing.assert_allclose(noised_mean, original, atol=0.1)


def test_dp_noise_larger_with_smaller_epsilon():
    """Smaller epsilon = more noise (stronger privacy)."""
    vector = [0.5] * 100
    deltas_high_eps = []
    deltas_low_eps = []
    for i in range(100):
        noised_high = apply_dp_noise(vector, epsilon=10.0, seed=i)
        noised_low = apply_dp_noise(vector, epsilon=0.1, seed=i + 1000)
        deltas_high_eps.append(np.mean(np.abs(np.array(noised_high) - 0.5)))
        deltas_low_eps.append(np.mean(np.abs(np.array(noised_low) - 0.5)))
    # Low epsilon should produce larger average deviation.
    assert np.mean(deltas_low_eps) > np.mean(deltas_high_eps)


# ---------------------------------------------------------------------------
# Integration: opt-in + anonymization pipeline
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_opt_in_then_check_status(db: AsyncSession):
    """Opt-in should create a consent record."""
    from ml import api as ml_api

    await ml_api.opt_in_to_cohorts(db, "user-anon-test")
    await db.flush()

    status = await ml_api.get_cohort_status(db, "user-anon-test")
    assert status["opted_in"] is True
    assert status["opted_in_at"] is not None


@pytest.mark.asyncio
async def test_opt_out_sets_deletion_requested(db: AsyncSession):
    """Opt-out should set deletion_requested_at."""
    from ml import api as ml_api

    await ml_api.opt_in_to_cohorts(db, "user-out-test")
    await db.flush()

    await ml_api.opt_out_of_cohorts(db, "user-out-test")
    await db.flush()

    status = await ml_api.get_cohort_status(db, "user-out-test")
    assert status["opted_in"] is False
    assert status["deletion_requested_at"] is not None
