"""Phase 4.5 Commit 4: wearables generator tests.

The load-bearing test here is
``test_steps_lag1_drives_sleep_efficiency`` — it pins the shared-latent
strength that lets L2 associations register the pair at
``developing+`` tier on 60-day data. Weakening it breaks Phase 5.9
Promptfoo active-patterns cases, so if the cohort size / window /
coefficient needs to change, update the coefficient in
``ml/synth/wearables.py`` and rerun this test.

Run: ``cd backend && uv run python -m pytest tests/ml/test_synth_wearables.py -v``
"""

from __future__ import annotations

import os

os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-must-be-long-enough-for-hs256-aaaaaaaa")
os.environ.setdefault("ENCRYPTION_KEY", "T0TXLkHFSeZRYGIIejSFVkhQrvRE-bWLkwXSkkdWiKQ=")
os.environ.setdefault("ANTHROPIC_API_KEY", "fake-key-tests-dont-call-anthropic")

from datetime import date

import numpy as np
import pytest

from ml.synth.demographics import generate_demographics
from ml.synth.wearables import WearableDay, generate_wearables


START = date(2026, 1, 1)


# ─────────────────────────────────────────────────────────────────────────
# Shape + determinism
# ─────────────────────────────────────────────────────────────────────────


def test_returns_flat_list_of_n_users_times_days() -> None:
    demo = generate_demographics(n_users=3, seed=42)
    rows = generate_wearables(demo, days=10, start_date=START, seed=42)
    assert len(rows) == 30


def test_is_deterministic_with_same_seed() -> None:
    demo = generate_demographics(n_users=5, seed=42)
    a = generate_wearables(demo, days=30, start_date=START, seed=42)
    b = generate_wearables(demo, days=30, start_date=START, seed=42)
    assert a == b


def test_different_seeds_produce_different_output() -> None:
    demo = generate_demographics(n_users=3, seed=42)
    a = generate_wearables(demo, days=30, start_date=START, seed=42)
    b = generate_wearables(demo, days=30, start_date=START, seed=43)
    assert a != b


def test_user_ids_match_demographics() -> None:
    demo = generate_demographics(n_users=4, seed=42)
    rows = generate_wearables(demo, days=7, start_date=START, seed=42)
    user_ids = {r.user_id for r in rows}
    assert user_ids == {d.user_id for d in demo}


def test_dates_are_iso_yyyy_mm_dd() -> None:
    """Load-bearing invariant #1 from the Phase 4.5 prep doc."""
    demo = generate_demographics(n_users=1, seed=42)
    rows = generate_wearables(demo, days=3, start_date=START, seed=42)
    assert [r.date for r in rows] == ["2026-01-01", "2026-01-02", "2026-01-03"]


def test_adding_more_users_does_not_shift_earlier_users_realizations() -> None:
    """SeedSequence.spawn guarantees this; pin it so a future refactor
    that switches to a shared rng cannot silently break downstream tests
    that hold the first user's series constant while varying cohort size."""
    small = generate_demographics(n_users=1, seed=42)
    big = generate_demographics(n_users=3, seed=42)
    small_rows = generate_wearables(small, days=14, start_date=START, seed=42)
    big_rows = generate_wearables(big, days=14, start_date=START, seed=42)
    # First user's 14 rows must match.
    first_user_from_big = [
        r for r in big_rows if r.user_id == small[0].user_id
    ]
    assert first_user_from_big == small_rows


# ─────────────────────────────────────────────────────────────────────────
# Range invariants
# ─────────────────────────────────────────────────────────────────────────


def _collect_present(rows: list[WearableDay], attr: str) -> list[float]:
    return [getattr(r, attr) for r in rows if getattr(r, attr) is not None]


def test_hrv_values_are_in_physiological_range() -> None:
    demo = generate_demographics(n_users=10, seed=11)
    rows = generate_wearables(demo, days=60, start_date=START, seed=11)
    hrv = _collect_present(rows, "hrv_average")
    assert hrv, "no hrv values emitted"
    assert all(15.0 <= v <= 150.0 for v in hrv)


def test_resting_hr_values_are_in_physiological_range() -> None:
    demo = generate_demographics(n_users=10, seed=11)
    rows = generate_wearables(demo, days=60, start_date=START, seed=11)
    rhr = _collect_present(rows, "resting_hr")
    assert rhr
    assert all(40.0 <= v <= 100.0 for v in rhr)


def test_sleep_efficiency_values_are_fractions() -> None:
    demo = generate_demographics(n_users=10, seed=11)
    rows = generate_wearables(demo, days=60, start_date=START, seed=11)
    eff = _collect_present(rows, "sleep_efficiency")
    assert eff
    assert all(0.5 <= v <= 1.0 for v in eff)


def test_readiness_is_integer_0_to_100() -> None:
    demo = generate_demographics(n_users=10, seed=11)
    rows = generate_wearables(demo, days=60, start_date=START, seed=11)
    r = _collect_present(rows, "readiness_score")
    assert r
    assert all(isinstance(v, int) and 0 <= v <= 100 for v in r)


def test_sleep_stages_sum_to_total_when_present() -> None:
    """Fidelity gate #3 in miniature: per-day, stages must add up cleanly
    to total_sleep_seconds on the rows that have sleep data."""
    demo = generate_demographics(n_users=5, seed=11)
    rows = generate_wearables(demo, days=30, start_date=START, seed=11)
    for r in rows:
        if r.total_sleep_seconds is None:
            assert r.deep_sleep_seconds is None
            assert r.rem_sleep_seconds is None
            assert r.light_sleep_seconds is None
            continue
        total = (
            (r.deep_sleep_seconds or 0)
            + (r.rem_sleep_seconds or 0)
            + (r.light_sleep_seconds or 0)
        )
        assert total == r.total_sleep_seconds, (
            f"{r.user_id}@{r.date}: stages {total} != total {r.total_sleep_seconds}"
        )


def test_steps_are_non_negative_integers() -> None:
    demo = generate_demographics(n_users=5, seed=11)
    rows = generate_wearables(demo, days=30, start_date=START, seed=11)
    steps = [r.steps for r in rows]
    assert all(isinstance(s, int) and s >= 0 for s in steps)


# ─────────────────────────────────────────────────────────────────────────
# Missingness calibration (invariant 3)
# ─────────────────────────────────────────────────────────────────────────


def test_biometric_missingness_stays_near_configured_target() -> None:
    """500-user cohort. HRV missingness should land in the +/- 3% band
    around the midpoint of the configured range."""
    demo = generate_demographics(n_users=500, seed=7)
    rows = generate_wearables(
        demo,
        days=30,
        start_date=START,
        seed=7,
        biometric_missingness=(0.12, 0.18),
    )
    hrv_total = len(rows)
    hrv_missing = sum(1 for r in rows if r.hrv_average is None)
    rate = hrv_missing / hrv_total
    # Target midpoint 0.15, tolerance +/- 0.03.
    assert 0.12 <= rate <= 0.18, f"HRV missingness {rate} outside target band"


def test_rejects_invalid_missingness_range() -> None:
    demo = generate_demographics(n_users=1, seed=7)
    with pytest.raises(ValueError):
        generate_wearables(
            demo,
            days=7,
            start_date=START,
            seed=7,
            biometric_missingness=(0.3, 0.1),  # low > high
        )
    with pytest.raises(ValueError):
        generate_wearables(
            demo, days=7, start_date=START, seed=7, biometric_missingness=(-0.1, 0.2)
        )


def test_rejects_zero_days() -> None:
    demo = generate_demographics(n_users=1, seed=7)
    with pytest.raises(ValueError):
        generate_wearables(demo, days=0, start_date=START, seed=7)


# ─────────────────────────────────────────────────────────────────────────
# Shared-latent invariant (the one Phase 5.9 depends on)
# ─────────────────────────────────────────────────────────────────────────


def test_steps_lag1_drives_sleep_efficiency() -> None:
    """Load-bearing: on 60-day data, steps[t-1] -> sleep_efficiency[t]
    Pearson r must be >= 0.30 pooled across users. L2 BH-FDR at
    alpha=0.10 treats r >= 0.30 on 30+ paired observations as
    developing-tier.

    If this test fails, tune the SLEEP_EFF_STEPS_LAG_COEF constant in
    ml/synth/wearables.py until it passes again. Do NOT loosen the
    threshold here without also updating Phase 5.9 fixtures."""
    demo = generate_demographics(n_users=20, seed=31)
    rows = generate_wearables(demo, days=60, start_date=START, seed=31)

    # Build (steps_prev, sleep_eff_today) pairs per user, pool, correlate.
    paired_steps: list[float] = []
    paired_eff: list[float] = []
    by_user: dict[str, list[WearableDay]] = {}
    for r in rows:
        by_user.setdefault(r.user_id, []).append(r)
    for days_row in by_user.values():
        days_row.sort(key=lambda d: d.date)
        for t in range(1, len(days_row)):
            prev_steps = days_row[t - 1].steps
            today_eff = days_row[t].sleep_efficiency
            if prev_steps is None or today_eff is None:
                continue
            paired_steps.append(float(prev_steps))
            paired_eff.append(today_eff)

    assert len(paired_steps) >= 500, (
        f"too few valid pairs ({len(paired_steps)}) to compute a reliable r"
    )
    r = float(np.corrcoef(paired_steps, paired_eff)[0, 1])
    assert r >= 0.30, (
        f"steps_lag1 -> sleep_efficiency r={r:.3f} below 0.30 floor. "
        f"Adjust SLEEP_EFF_STEPS_LAG_COEF in wearables.py."
    )


def test_wellness_latent_couples_hrv_and_readiness() -> None:
    """Secondary cross-channel check: HRV and readiness both ride the
    same per-user wellness latent, so pooled same-day correlation should
    be clearly positive (>= 0.40) on 60-day data."""
    demo = generate_demographics(n_users=20, seed=19)
    rows = generate_wearables(demo, days=60, start_date=START, seed=19)
    pairs_h: list[float] = []
    pairs_r: list[float] = []
    for r in rows:
        if r.hrv_average is None or r.readiness_score is None:
            continue
        pairs_h.append(r.hrv_average)
        pairs_r.append(float(r.readiness_score))
    rho = float(np.corrcoef(pairs_h, pairs_r)[0, 1])
    assert rho >= 0.40, f"HRV/readiness shared-latent r={rho:.3f} below 0.40"


def test_weekend_steps_are_lower_than_weekday_on_average() -> None:
    """Day-of-week effect is part of the parametric spec; a cohort
    average should clearly show it."""
    demo = generate_demographics(n_users=30, seed=3)
    rows = generate_wearables(demo, days=60, start_date=START, seed=3)
    weekday_steps: list[int] = []
    weekend_steps: list[int] = []
    from datetime import date as _date

    for r in rows:
        d = _date.fromisoformat(r.date)
        if r.steps is None:
            continue
        if d.weekday() < 5:
            weekday_steps.append(r.steps)
        else:
            weekend_steps.append(r.steps)
    assert weekday_steps and weekend_steps
    wd_mean = sum(weekday_steps) / len(weekday_steps)
    we_mean = sum(weekend_steps) / len(weekend_steps)
    assert we_mean < wd_mean, (
        f"weekend mean {we_mean:.0f} not below weekday mean {wd_mean:.0f}"
    )
