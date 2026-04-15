"""Phase 4.5 Commit 4: demographics generator tests.

Pin the determinism + range invariants the wearables generator and the
fidelity suite (Commit 7) rely on.

Run: ``cd backend && uv run python -m pytest tests/ml/test_synth_demographics.py -v``
"""

from __future__ import annotations

import os

os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-must-be-long-enough-for-hs256-aaaaaaaa")
os.environ.setdefault("ENCRYPTION_KEY", "T0TXLkHFSeZRYGIIejSFVkhQrvRE-bWLkwXSkkdWiKQ=")
os.environ.setdefault("ANTHROPIC_API_KEY", "fake-key-tests-dont-call-anthropic")

from dataclasses import FrozenInstanceError

import pytest

from ml.synth.demographics import Demographics, generate_demographics


# ─────────────────────────────────────────────────────────────────────────
# Determinism
# ─────────────────────────────────────────────────────────────────────────


def test_returns_requested_count() -> None:
    assert len(generate_demographics(n_users=10, seed=42)) == 10


def test_is_deterministic_with_same_seed() -> None:
    """Same seed, identical output. The whole synth pipeline hinges on this."""
    a = generate_demographics(n_users=25, seed=42)
    b = generate_demographics(n_users=25, seed=42)
    assert a == b


def test_different_seeds_produce_different_output() -> None:
    a = generate_demographics(n_users=25, seed=42)
    b = generate_demographics(n_users=25, seed=43)
    assert a != b


def test_unseeded_generations_are_distinct() -> None:
    """seed=None must not be deterministic across calls."""
    a = generate_demographics(n_users=25, seed=None)
    b = generate_demographics(n_users=25, seed=None)
    # IDs use uuid4 in the unseeded path so collision is practically zero.
    assert [d.user_id for d in a] != [d.user_id for d in b]


# ─────────────────────────────────────────────────────────────────────────
# Range invariants
# ─────────────────────────────────────────────────────────────────────────


def test_ages_fall_within_configured_range() -> None:
    demo = generate_demographics(n_users=200, seed=7)
    assert all(25 <= d.age <= 75 for d in demo)


def test_bmi_falls_within_configured_range() -> None:
    demo = generate_demographics(n_users=200, seed=7)
    assert all(18.5 <= d.bmi <= 42.0 for d in demo)


def test_sex_distribution_is_approximately_balanced() -> None:
    """500-draw chi-square tolerance band; well inside CLT bounds."""
    demo = generate_demographics(n_users=500, seed=7)
    n_female = sum(1 for d in demo if d.sex == "female")
    assert 200 <= n_female <= 300, f"got {n_female} female of 500"


def test_comorbidities_are_subset_of_known_vocabulary() -> None:
    known = {"hypertension", "insomnia", "anxiety", "t2_diabetes"}
    demo = generate_demographics(n_users=200, seed=7)
    for d in demo:
        assert set(d.comorbidities).issubset(known), d.comorbidities


def test_comorbidities_are_sorted() -> None:
    """Stable equality relies on canonical ordering."""
    demo = generate_demographics(n_users=200, seed=7)
    for d in demo:
        assert list(d.comorbidities) == sorted(d.comorbidities)


# ─────────────────────────────────────────────────────────────────────────
# User id invariants
# ─────────────────────────────────────────────────────────────────────────


def test_user_ids_are_unique_within_a_seeded_cohort() -> None:
    demo = generate_demographics(n_users=200, seed=7)
    ids = [d.user_id for d in demo]
    assert len(set(ids)) == len(ids)


def test_user_ids_have_synth_prefix() -> None:
    """Greppable by design. Real-user ids never start with ``synth-``."""
    demo = generate_demographics(n_users=10, seed=7)
    assert all(d.user_id.startswith("synth-") for d in demo)


def test_seeded_and_unseeded_cohort_user_ids_do_not_collide() -> None:
    """uuid5 (seeded path) and uuid4 (unseeded) use different variant bits,
    so the namespaces cannot overlap. Defensive check in case someone
    later changes the id composition."""
    seeded = {d.user_id for d in generate_demographics(n_users=50, seed=7)}
    unseeded = {d.user_id for d in generate_demographics(n_users=50, seed=None)}
    assert seeded.isdisjoint(unseeded)


# ─────────────────────────────────────────────────────────────────────────
# Error handling
# ─────────────────────────────────────────────────────────────────────────


def test_zero_users_is_valid_and_returns_empty_list() -> None:
    assert generate_demographics(n_users=0, seed=42) == []


def test_negative_n_users_raises_value_error() -> None:
    with pytest.raises(ValueError):
        generate_demographics(n_users=-1, seed=42)


# ─────────────────────────────────────────────────────────────────────────
# Immutability
# ─────────────────────────────────────────────────────────────────────────


def test_demographics_dataclass_is_frozen() -> None:
    """Shared-input invariant: downstream generators must not mutate
    the demographics record they receive. Frozen=True enforces this at
    the dataclass level."""
    demo = generate_demographics(n_users=1, seed=42)[0]
    assert isinstance(demo, Demographics)
    with pytest.raises(FrozenInstanceError):
        demo.age = 99  # type: ignore[misc]
