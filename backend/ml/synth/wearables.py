"""Parametric wearables generator for the Phase 4.5 synth factory.

Produces per-user-per-day biometric + activity records driven by a
per-user AR(1) wellness latent that modulates every channel. The shared
latent is the whole point: without it, the downstream discovery layers
see independently-sampled noise and nothing promotes to ``developing+``
tier, so Phase 5.9 Promptfoo active-patterns cases have no signal to
match against.

Non-negotiable invariants pinned by ``tests/ml/test_synth_wearables.py``
(and re-checked at the cohort level by Commit 7's fidelity suite):

1. Deterministic with seed. Same ``(demographics, days, start_date,
   seed)`` input yields byte-identical output, every time.
2. Cross-channel coupling strong enough that on 60 days of data
   ``steps[t-1]`` -> ``sleep_efficiency[t]`` shows Pearson r >= 0.30,
   which is what L2 BH-FDR needs to reach ``developing`` tier.
3. Biometric missingness sampled from the configured range (default
   0.12-0.18). A 500-user cohort stays inside +/- 3% of that band.

Top-level numpy import is allowed per the Phase 4.5 scaffolding plan:
numpy is already a backend dep and the factory orchestrator lazy-loads
this module anyway, so no cold-boot regression.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np

from ml.synth.demographics import Demographics


# ── AR(1) wellness latent ───────────────────────────────────────────────

# phi=0.85 sits in the middle of published adult HRV autocorrelation
# ranges. The noise sd is set so the stationary variance of wellness is
# exactly 1, which keeps the downstream coefficient tuning predictable
# (each channel multiplies the latent by its own small weight).
_PHI = 0.85
_WELLNESS_NOISE_SD = float(np.sqrt(1.0 - _PHI * _PHI))


# ── Channel parameters. Baselines track published adult ranges. ─────────

_HRV_BASELINE = 50.0  # ms
_HRV_LATENT_COEF = 0.25  # log-scale
_HRV_NOISE_SD = 0.12  # log-scale per-day shock
_HRV_MIN, _HRV_MAX = 15.0, 150.0

_RHR_BASELINE = 60.0  # bpm
_RHR_LATENT_COEF = -0.08  # log-scale, inversely correlated with wellness
_RHR_NOISE_SD = 2.0  # bpm additive
_RHR_MIN, _RHR_MAX = 40.0, 100.0

# Sleep efficiency: latent drives the baseline, plus a lag-1 effect from
# the previous day's (standardized) steps. The steps coefficient is the
# load-bearing parameter for invariant 2 above.
_SLEEP_EFF_BASE = 0.80
_SLEEP_EFF_LATENT_COEF = 0.04
_SLEEP_EFF_STEPS_LAG_COEF = 0.05
_SLEEP_EFF_NOISE_SD = 0.02
_SLEEP_EFF_MIN, _SLEEP_EFF_MAX = 0.50, 1.0

_READINESS_BASELINE = 60.0
_READINESS_LATENT_COEF = 20.0
_READINESS_NOISE_SD = 5.0
_READINESS_MIN, _READINESS_MAX = 10, 100

_STEPS_BASELINE = 8000.0
_STEPS_WEEKEND_MULT = 0.70
_STEPS_LATENT_COEF = 3000.0
_STEPS_NOISE_SD = 1000.0
_STEPS_ZERO_INFLATION_P = 0.05

_SLEEP_DURATION_BASE_S = 25_200  # 7 h
_SLEEP_DURATION_RANGE_S = 3_600  # +/- 1 h scaled by sleep_eff
_SLEEP_DURATION_MIN_S = 10_800  # 3 h
_SLEEP_DURATION_MAX_S = 36_000  # 10 h

_DEEP_SLEEP_FRAC = 0.18
_REM_SLEEP_FRAC = 0.22
_SLEEP_STAGE_NOISE_SD = 0.02

_ACTIVE_CAL_PER_STEP = 0.045
_ACTIVE_CAL_NOISE_SD = 50.0
_ACTIVE_CAL_MAX = 2_000

_WORKOUT_P = 0.30
_WORKOUT_TYPES = ("run", "strength", "cycle", "yoga")
_WORKOUT_MIN_S = 1_200  # 20 min
_WORKOUT_MAX_S = 5_400  # 90 min

# Comorbidity adjustments on the HRV baseline (log-scale). Lower HRV is
# consistent with each of these conditions in the adult literature; the
# magnitudes are deliberately conservative so the discovery pipeline
# still sees the main within-user latent signal, not a cohort-effect
# artifact.
_COMORBIDITY_HRV_SHIFT: dict[str, float] = {
    "insomnia": -0.20,
    "anxiety": -0.10,
    "t2_diabetes": -0.15,
    "hypertension": -0.05,
}

# BMI also nudges the HRV baseline downward for the high end of the
# range, and resting heart rate upward. Linear in BMI above 28.
_BMI_HRV_REFERENCE = 25.0
_BMI_HRV_COEF = -0.015  # per BMI unit above reference, log-scale
_BMI_RHR_COEF = 0.010  # per BMI unit above reference, log-scale


@dataclass
class WearableDay:
    """One synth user's biometric + activity record for one day.

    Every metric field may be ``None`` to represent a non-observed
    reading. The factory orchestrator skips writing a raw-table row when
    its driving field is None, which mirrors how real ingestion paths
    produce sparse raw tables.
    """

    user_id: str
    date: str  # YYYY-MM-DD
    # Sleep channels
    sleep_efficiency: float | None
    total_sleep_seconds: int | None
    deep_sleep_seconds: int | None
    rem_sleep_seconds: int | None
    light_sleep_seconds: int | None
    hrv_average: float | None
    resting_hr: float | None
    readiness_score: int | None
    bedtime_start: str | None
    bedtime_end: str | None
    # Activity channels
    steps: int | None
    active_calories: int | None
    workout_type: str | None
    workout_duration_seconds: int | None


# ─────────────────────────────────────────────────────────────────────────
# Internal per-user series generation
# ─────────────────────────────────────────────────────────────────────────


def _ar1_wellness(days: int, rng: np.random.Generator) -> np.ndarray:
    """Return a ``days``-length AR(1) wellness series with stationary var=1.

    The series is drawn from the stationary distribution at t=0 so the
    first few days are not systematically damped toward zero; this keeps
    a 28-day window (the L1 baseline minimum) statistically comparable
    to a 120-day window.
    """
    w = np.empty(days, dtype=np.float64)
    w[0] = rng.standard_normal()
    noise = rng.standard_normal(days - 1) * _WELLNESS_NOISE_SD
    for t in range(1, days):
        w[t] = _PHI * w[t - 1] + noise[t - 1]
    return w


def _baseline_hrv_shift(demo: Demographics) -> float:
    """Log-scale HRV adjustment from demographics + comorbidities."""
    shift = 0.0
    for c in demo.comorbidities:
        shift += _COMORBIDITY_HRV_SHIFT.get(c, 0.0)
    if demo.bmi > _BMI_HRV_REFERENCE:
        shift += _BMI_HRV_COEF * (demo.bmi - _BMI_HRV_REFERENCE)
    return shift


def _baseline_rhr_shift(demo: Demographics) -> float:
    """Log-scale RHR adjustment from BMI. Higher BMI, higher RHR."""
    if demo.bmi <= _BMI_HRV_REFERENCE:
        return 0.0
    return _BMI_RHR_COEF * (demo.bmi - _BMI_HRV_REFERENCE)


def _generate_user_series(
    demo: Demographics,
    days: int,
    start_date: date,
    rng: np.random.Generator,
    biometric_missingness_rate: float,
) -> list[WearableDay]:
    """Generate one user's full ``days``-length timeseries."""
    wellness = _ar1_wellness(days, rng)

    # ── Day-of-week + date strings ──
    dows = np.array(
        [(start_date + timedelta(days=t)).weekday() for t in range(days)]
    )
    weekday_mult = np.where(dows < 5, 1.0, _STEPS_WEEKEND_MULT)
    date_strs = [
        (start_date + timedelta(days=t)).isoformat() for t in range(days)
    ]

    # ── Steps (day-of-week + wellness + noise, zero-inflated) ──
    steps_base = _STEPS_BASELINE * weekday_mult + _STEPS_LATENT_COEF * wellness
    steps_noise = _STEPS_NOISE_SD * rng.standard_normal(days)
    steps = np.maximum(0.0, steps_base + steps_noise)
    zero_days = rng.random(days) < _STEPS_ZERO_INFLATION_P
    steps = np.where(zero_days, 0.0, steps)
    steps_int = steps.astype(np.int64)

    # Standardized steps lag: drives sleep_efficiency[t] from steps[t-1].
    # Day 0 has no lag signal; zero-lag keeps the math clean.
    steps_standardized = (steps - _STEPS_BASELINE) / _STEPS_LATENT_COEF
    steps_lag1 = np.concatenate([[0.0], steps_standardized[:-1]])

    # ── HRV (log-normal around adjusted baseline) ──
    hrv_shift = _baseline_hrv_shift(demo)
    hrv_log = (
        np.log(_HRV_BASELINE)
        + hrv_shift
        + _HRV_LATENT_COEF * wellness
        + _HRV_NOISE_SD * rng.standard_normal(days)
    )
    hrv = np.clip(np.exp(hrv_log), _HRV_MIN, _HRV_MAX)

    # ── Resting HR (log-normal, inverse of wellness) ──
    rhr_log = (
        np.log(_RHR_BASELINE)
        + _baseline_rhr_shift(demo)
        + _RHR_LATENT_COEF * wellness
    )
    rhr = np.clip(
        np.exp(rhr_log) + _RHR_NOISE_SD * rng.standard_normal(days),
        _RHR_MIN,
        _RHR_MAX,
    )

    # ── Sleep efficiency ──
    sleep_eff = (
        _SLEEP_EFF_BASE
        + _SLEEP_EFF_LATENT_COEF * wellness
        + _SLEEP_EFF_STEPS_LAG_COEF * steps_lag1
        + _SLEEP_EFF_NOISE_SD * rng.standard_normal(days)
    )
    sleep_eff = np.clip(sleep_eff, _SLEEP_EFF_MIN, _SLEEP_EFF_MAX)

    # ── Sleep duration (scaled by sleep_eff) ──
    total_sleep = _SLEEP_DURATION_BASE_S + _SLEEP_DURATION_RANGE_S * (
        sleep_eff - _SLEEP_EFF_BASE
    )
    total_sleep = np.clip(
        total_sleep, _SLEEP_DURATION_MIN_S, _SLEEP_DURATION_MAX_S
    ).astype(np.int64)

    # Stage breakdown with a small noise term on the fractions.
    deep_frac = np.clip(
        _DEEP_SLEEP_FRAC + _SLEEP_STAGE_NOISE_SD * rng.standard_normal(days),
        0.08,
        0.30,
    )
    rem_frac = np.clip(
        _REM_SLEEP_FRAC + _SLEEP_STAGE_NOISE_SD * rng.standard_normal(days),
        0.10,
        0.35,
    )
    deep_sleep = (total_sleep * deep_frac).astype(np.int64)
    rem_sleep = (total_sleep * rem_frac).astype(np.int64)
    light_sleep = total_sleep - deep_sleep - rem_sleep

    # ── Readiness score ──
    readiness_raw = (
        _READINESS_BASELINE
        + _READINESS_LATENT_COEF * wellness
        + _READINESS_NOISE_SD * rng.standard_normal(days)
    )
    readiness = np.clip(
        np.round(readiness_raw).astype(np.int64),
        _READINESS_MIN,
        _READINESS_MAX,
    )

    # ── Active calories (driven by steps with noise) ──
    active_cal_raw = (
        steps * _ACTIVE_CAL_PER_STEP
        + _ACTIVE_CAL_NOISE_SD * rng.standard_normal(days)
    )
    active_cal = np.clip(
        np.round(active_cal_raw).astype(np.int64), 0, _ACTIVE_CAL_MAX
    )

    # ── Workouts (30% of days) ──
    has_workout = rng.random(days) < _WORKOUT_P
    workout_type_idx = rng.integers(0, len(_WORKOUT_TYPES), size=days)
    workout_duration = rng.integers(_WORKOUT_MIN_S, _WORKOUT_MAX_S, size=days)

    # ── Bedtimes (canonical 22:30/06:30, nudged slightly by wellness) ──
    start_offsets = np.round(rng.standard_normal(days) * 30).astype(np.int64)
    end_offsets = np.round(rng.standard_normal(days) * 30).astype(np.int64)

    # ── Missingness masks (per-channel independent Bernoulli per day) ──
    def _miss_mask() -> np.ndarray:
        return rng.random(days) < biometric_missingness_rate

    sleep_eff_missing = _miss_mask()
    hrv_missing = _miss_mask()
    rhr_missing = _miss_mask()
    readiness_missing = _miss_mask()
    # Sleep duration + stages share a mask (all from the same ring data source).
    sleep_duration_missing = _miss_mask()

    # ── Assemble WearableDay records ──
    out: list[WearableDay] = []
    for t in range(days):
        bedtime_start = _fmt_time(22, 30, int(start_offsets[t]))
        bedtime_end = _fmt_time(6, 30, int(end_offsets[t]))

        w_type = _WORKOUT_TYPES[int(workout_type_idx[t])] if has_workout[t] else None
        w_dur = int(workout_duration[t]) if has_workout[t] else None

        out.append(
            WearableDay(
                user_id=demo.user_id,
                date=date_strs[t],
                sleep_efficiency=None
                if sleep_eff_missing[t]
                else float(round(sleep_eff[t], 4)),
                total_sleep_seconds=None
                if sleep_duration_missing[t]
                else int(total_sleep[t]),
                deep_sleep_seconds=None
                if sleep_duration_missing[t]
                else int(deep_sleep[t]),
                rem_sleep_seconds=None
                if sleep_duration_missing[t]
                else int(rem_sleep[t]),
                light_sleep_seconds=None
                if sleep_duration_missing[t]
                else int(light_sleep[t]),
                hrv_average=None
                if hrv_missing[t]
                else float(round(hrv[t], 2)),
                resting_hr=None
                if rhr_missing[t]
                else float(round(rhr[t], 2)),
                readiness_score=None
                if readiness_missing[t]
                else int(readiness[t]),
                bedtime_start=None if sleep_duration_missing[t] else bedtime_start,
                bedtime_end=None if sleep_duration_missing[t] else bedtime_end,
                steps=int(steps_int[t]),
                active_calories=int(active_cal[t]),
                workout_type=w_type,
                workout_duration_seconds=w_dur,
            )
        )
    return out


def _fmt_time(hour: int, minute: int, offset_minutes: int) -> str:
    """Return ``HH:MM`` after adding ``offset_minutes`` (mod 24h)."""
    total = (hour * 60 + minute + offset_minutes) % (24 * 60)
    return f"{total // 60:02d}:{total % 60:02d}"


# ─────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────


def generate_wearables(
    demographics: list[Demographics],
    days: int,
    start_date: date,
    seed: int | None = None,
    biometric_missingness: tuple[float, float] = (0.12, 0.18),
) -> list[WearableDay]:
    """Return a flat list of ``WearableDay`` sorted by (user_id, date).

    Deterministic with seed. Each user gets a fresh sub-generator spawned
    off a SeedSequence so adding users to a cohort does not shift the
    realizations of earlier users' series.
    """
    if days < 1:
        raise ValueError(f"days must be >= 1, got {days}")
    low, high = biometric_missingness
    if not (0.0 <= low <= high <= 1.0):
        raise ValueError(
            f"biometric_missingness must be 0 <= low <= high <= 1, got {biometric_missingness}"
        )
    ss = np.random.SeedSequence(seed)
    out: list[WearableDay] = []
    # Spawn one child sequence per user so the top-level seed stays
    # invariant to the number of users requested. This matters for
    # reproducibility across cohort sizes.
    child_seeds = ss.spawn(len(demographics))
    for demo, child_seed in zip(demographics, child_seeds):
        user_rng = np.random.default_rng(child_seed)
        # Per-user missingness rate uniform in [low, high] so the cohort
        # average lands on the midpoint and invariant 3 holds.
        rate = float(user_rng.uniform(low, high))
        out.extend(
            _generate_user_series(
                demo=demo,
                days=days,
                start_date=start_date,
                rng=user_rng,
                biometric_missingness_rate=rate,
            )
        )
    return out


__all__ = ["WearableDay", "generate_wearables"]
