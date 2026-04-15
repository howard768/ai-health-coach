"""Synthea-inspired demographic generator for synth cohorts.

Phase 4.5 Commit 4, the first step of the synth factory pipeline.

This module does not shell out to the Synthea CLI. Synthea is a Java
binary; pulling it at test time would break the cold-boot budget and
offer no benefit at the cohort sizes the discovery pipeline needs. The
output shape mirrors Synthea's: age in years, binary sex, BMI with a
mildly tail-heavy distribution, and a sparse multi-label comorbidity
vector drawn from the short list that actually modulates the biometric
ranges the wearables generator produces.

Distribution targets loosely track NHANES 2017-2020 adult ranges. They
are conservative on purpose: the synth factory's job is to exercise
every discovery layer on plausible data, not to mimic any real
population.

Deterministic with ``seed``. Same seed, same output, every time. The
tests in ``tests/ml/test_synth_demographics.py`` pin the guarantee.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass


# ── Distribution parameters. See module docstring for rationale. ──

_MIN_AGE = 25
_MAX_AGE = 75

_BMI_MEAN = 26.5
_BMI_SD = 5.2
# 18.5 is the WHO underweight cutoff. Below, a user is outside the coaching
# population. 42 caps at severe-obesity; synth beyond that just widens
# downstream ranges without exercising a new discovery-layer path.
_BMI_MIN = 18.5
_BMI_MAX = 42.0

# Comorbidities whose presence actually shifts the synth biometric ranges the
# wearables generator produces. Keeping this list short keeps the
# combinatorial space the generator has to reason over small. If you add one,
# make sure wearables.py knows how to respond to it.
_COMORBIDITY_PREVALENCE: dict[str, float] = {
    "hypertension": 0.30,
    "insomnia": 0.15,
    "anxiety": 0.18,
    "t2_diabetes": 0.10,
}

# UUID5 namespace so (seed, index) pairs map to a stable, reproducible user
# id. Swapping to a fresh uuid4 (for seed=None) never collides with a seeded
# id because uuid5 uses the DNS namespace + our own salt prefix.
_USER_ID_NAMESPACE = uuid.NAMESPACE_DNS
_USER_ID_SALT = "meld-synth"


@dataclass(frozen=True)
class Demographics:
    """Per-synth-user demographic state.

    Immutable (``frozen=True``) so downstream generators cannot mutate a
    shared demographics record when the same synth user is consumed by
    multiple generator stages (wearables, conversations, meal logs).
    """

    user_id: str
    age: int
    sex: str  # "female" | "male"
    bmi: float
    comorbidities: tuple[str, ...]


def _draw_bmi(rng: random.Random) -> float:
    """Clipped Gaussian BMI draw rounded to one decimal place.

    Resamples up to 16 times to find a draw inside the support, which is
    generous: at the default mean and sd the CDF outside ``[18.5, 42]``
    is roughly 5% so rejection sampling converges in 1-2 tries on
    average. The bound keeps the loop honest if someone later tightens
    the range; on exhaustion we fall back to the mean rather than
    loop forever.
    """
    for _ in range(16):
        candidate = rng.gauss(_BMI_MEAN, _BMI_SD)
        if _BMI_MIN <= candidate <= _BMI_MAX:
            return round(candidate, 1)
    return _BMI_MEAN


def _draw_comorbidities(rng: random.Random) -> tuple[str, ...]:
    """Independent Bernoulli draws per comorbidity. Sorted for stable equality."""
    hits = [
        name
        for name, p in _COMORBIDITY_PREVALENCE.items()
        if rng.random() < p
    ]
    return tuple(sorted(hits))


def _make_user_id(seed: int | None, index: int) -> str:
    """Return a user id of the form ``synth-<12 hex chars>``.

    Seeded case: uuid5 over ``(seed, index)`` gives identical ids across
    runs, which every downstream test relies on for stability. Unseeded
    case: uuid4 so two unseeded cohorts never collide with each other
    or with a seeded one (uuid4 uses a distinct variant bit).
    """
    if seed is None:
        return f"synth-{uuid.uuid4().hex[:12]}"
    composed = f"{_USER_ID_SALT}-{seed}-{index}"
    return f"synth-{uuid.uuid5(_USER_ID_NAMESPACE, composed).hex[:12]}"


def generate_demographics(
    n_users: int,
    seed: int | None = None,
) -> list[Demographics]:
    """Return ``n_users`` reproducible ``Demographics`` records.

    ``seed=None`` means a fresh non-deterministic cohort. Passing an
    integer makes the full sequence (ids, ages, sexes, BMIs,
    comorbidities) identical across runs, which is what every test in
    ``tests/ml/test_synth*`` relies on.
    """
    if n_users < 0:
        raise ValueError(f"n_users must be >= 0, got {n_users}")
    rng = random.Random(seed)
    out: list[Demographics] = []
    for i in range(n_users):
        user_id = _make_user_id(seed, i)
        age = rng.randint(_MIN_AGE, _MAX_AGE)
        sex = "female" if rng.random() < 0.5 else "male"
        bmi = _draw_bmi(rng)
        comorbidities = _draw_comorbidities(rng)
        out.append(
            Demographics(
                user_id=user_id,
                age=age,
                sex=sex,
                bmi=bmi,
                comorbidities=comorbidities,
            )
        )
    return out


__all__ = ["Demographics", "generate_demographics"]
