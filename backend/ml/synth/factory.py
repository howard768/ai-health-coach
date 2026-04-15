"""Phase 4.5 synth factory orchestrator.

``generate_cohort`` is the one function that does the composition:

1. Resolve defaults from ``MLSettings`` when the caller left them None.
2. Generate ``Demographics`` for ``n_users``.
3. Generate ``WearableDay`` timeseries (parametric or GAN).
4. Generate meal records inline (nutrition is not its own module
   because the meal generator is small and its only consumer is the
   factory).
5. Write every row to the raw tables with ``is_synthetic=True``.
6. Return a ``CohortManifest``.

What this orchestrator does NOT do, on purpose:

- **Does not commit.** The caller owns the transaction, matching every
  other async entry point in ``ml.api``.
- **Does not generate coach conversations.** The conversations module
  exists as a sibling (tested on its own); the fixture-consumer in
  Phase 5.9 invokes it directly. Keeping the factory focused on raw
  tables keeps the boundary between "data the discovery pipeline
  reads" and "fixtures the Promptfoo harness reads" sharp.

Invariants pinned by ``tests/ml/test_synth_factory.py``:

1. Every row written carries ``is_synthetic=True``.
2. Dates are ``String(10)`` ``YYYY-MM-DD`` at every write (load-
   bearing invariant #1 in the Phase 4.5 prep doc).
3. Deterministic with seed.
4. The manifest's ``user_ids`` match the demographics that were
   actually written.
5. No bare ``datetime`` ever reaches a model constructor for the
   ``date`` column; ``MealRecord.created_at`` is the only datetime
   field and it encodes dinner hour by design.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import TYPE_CHECKING

from ml.synth.demographics import Demographics, generate_demographics
from ml.synth.wearables import WearableDay, generate_wearables

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from ml.api import CohortManifest


# ── Source tag used on every synth row so downstream filters (crisis
# evals, production aggregates) can match on `source == "synth"` in
# addition to the authoritative `is_synthetic = True` check. Belt and
# braces. ──
_SYNTH_SOURCE = "synth"


# ── Meal generation parameters. Kept here rather than in a separate
# module because the meal generator is small and the factory is the only
# caller. ──
_MEAL_TYPES = ("breakfast", "lunch", "dinner")

# Per-meal nominal hours. Dinner hour is the interesting one for the
# ``dinner_hour`` feature (Commit 2); it is drawn per day from a user-
# anchored normal distribution below.
_BREAKFAST_HOUR = 8
_LUNCH_HOUR = 12

# Dinner hour: N(user_mean, 1.0), clipped to [17, 22]. Each user's mean
# is pulled once from U(18, 20) so the cohort has variety.
_DINNER_USER_MEAN_LOW = 18.0
_DINNER_USER_MEAN_HIGH = 20.0
_DINNER_NOISE_SD = 1.0
_DINNER_HOUR_MIN = 17
_DINNER_HOUR_MAX = 22

# Simple food catalog. Three items per meal type, one picked at random.
# Macros track published adult-serving approximations; this is not an
# accuracy claim, only a source of plausible per-meal rows for the
# downstream feature builders to consume.
_FOOD_CATALOG: dict[str, list[dict]] = {
    "breakfast": [
        {
            "name": "oatmeal with berries",
            "serving_size": "1 cup",
            "calories": 310,
            "protein": 9.0,
            "carbs": 58.0,
            "fat": 5.0,
            "quality": "whole",
        },
        {
            "name": "greek yogurt parfait",
            "serving_size": "1 cup",
            "calories": 260,
            "protein": 18.0,
            "carbs": 32.0,
            "fat": 6.0,
            "quality": "whole",
        },
        {
            "name": "scrambled eggs and toast",
            "serving_size": "2 eggs plus 1 slice",
            "calories": 350,
            "protein": 20.0,
            "carbs": 24.0,
            "fat": 18.0,
            "quality": "mixed",
        },
    ],
    "lunch": [
        {
            "name": "chicken salad bowl",
            "serving_size": "1 bowl",
            "calories": 520,
            "protein": 38.0,
            "carbs": 42.0,
            "fat": 22.0,
            "quality": "whole",
        },
        {
            "name": "turkey sandwich",
            "serving_size": "1 sandwich",
            "calories": 480,
            "protein": 28.0,
            "carbs": 52.0,
            "fat": 16.0,
            "quality": "mixed",
        },
        {
            "name": "veggie burrito",
            "serving_size": "1 burrito",
            "calories": 620,
            "protein": 20.0,
            "carbs": 78.0,
            "fat": 22.0,
            "quality": "mixed",
        },
    ],
    "dinner": [
        {
            "name": "grilled salmon with rice",
            "serving_size": "6 oz plus 1 cup",
            "calories": 580,
            "protein": 38.0,
            "carbs": 54.0,
            "fat": 22.0,
            "quality": "whole",
        },
        {
            "name": "pasta primavera",
            "serving_size": "1 plate",
            "calories": 640,
            "protein": 20.0,
            "carbs": 92.0,
            "fat": 20.0,
            "quality": "mixed",
        },
        {
            "name": "roast chicken and vegetables",
            "serving_size": "1 plate",
            "calories": 560,
            "protein": 44.0,
            "carbs": 40.0,
            "fat": 20.0,
            "quality": "whole",
        },
    ],
}


@dataclass
class _SynthMeal:
    """Intermediate shape for a generated meal, before ORM row writing."""

    user_id: str
    date: str
    meal_type: str
    created_at: datetime
    item: dict


def _generate_meals(
    demographics: list[Demographics],
    days: int,
    start_date: date,
    seed: int | None,
    manual_log_missingness: tuple[float, float],
) -> list[_SynthMeal]:
    """Emit meals for every user-day, applying per-user missingness.

    Each user gets a personal dinner hour ``mu`` and a personal
    log-missingness rate drawn from the configured band, so two users
    with different personas end up with different manual-log behaviors.
    """
    low, high = manual_log_missingness
    if not (0.0 <= low <= high <= 1.0):
        raise ValueError(
            f"manual_log_missingness must be 0 <= low <= high <= 1, got ({low}, {high})"
        )
    rng = random.Random(seed)
    out: list[_SynthMeal] = []
    for demo in demographics:
        # Per-user seed so adding users leaves earlier users' meal
        # sequences invariant (same spirit as the wearables SeedSequence
        # spawn trick).
        user_seed = rng.randrange(1 << 32)
        user_rng = random.Random(user_seed)
        missing_rate = user_rng.uniform(low, high)
        dinner_mean_hour = user_rng.uniform(
            _DINNER_USER_MEAN_LOW, _DINNER_USER_MEAN_HIGH
        )

        for d_offset in range(days):
            d = start_date + timedelta(days=d_offset)
            d_iso = d.isoformat()

            for meal_type in _MEAL_TYPES:
                if user_rng.random() < missing_rate:
                    continue  # skipped meal log
                if meal_type == "breakfast":
                    hour = _BREAKFAST_HOUR
                    minute = user_rng.randint(0, 45)
                elif meal_type == "lunch":
                    hour = _LUNCH_HOUR
                    minute = user_rng.randint(0, 45)
                else:
                    raw_hour = user_rng.gauss(dinner_mean_hour, _DINNER_NOISE_SD)
                    hour = int(min(_DINNER_HOUR_MAX, max(_DINNER_HOUR_MIN, round(raw_hour))))
                    minute = user_rng.randint(0, 55)

                created_at = datetime.combine(d, time(hour=hour, minute=minute))
                item = user_rng.choice(_FOOD_CATALOG[meal_type])

                out.append(
                    _SynthMeal(
                        user_id=demo.user_id,
                        date=d_iso,
                        meal_type=meal_type,
                        created_at=created_at,
                        item=item,
                    )
                )
    return out


# ─────────────────────────────────────────────────────────────────────────
# ORM write helpers
# ─────────────────────────────────────────────────────────────────────────


def _wearable_to_health_metric_rows(wd: WearableDay):
    """Yield HealthMetricRecord instances for the five canonical biometrics.

    Mirrors ``ml.features.builders.BIOMETRIC_METRIC_TYPES``: hrv,
    resting_hr, sleep_efficiency, sleep_duration (seconds),
    readiness_score. Rows with a missing source field (None on the
    WearableDay) are simply skipped so raw-table sparsity tracks the
    configured missingness band.
    """
    from app.models.health import HealthMetricRecord

    entries: list[tuple[str, float | int | None, str | None]] = [
        ("hrv", wd.hrv_average, "ms"),
        ("resting_hr", wd.resting_hr, "bpm"),
        ("sleep_efficiency", wd.sleep_efficiency, None),
        ("sleep_duration", wd.total_sleep_seconds, "seconds"),
        ("readiness_score", wd.readiness_score, None),
    ]
    for metric_type, value, unit in entries:
        if value is None:
            continue
        yield HealthMetricRecord(
            user_id=wd.user_id,
            date=wd.date,
            metric_type=metric_type,
            value=float(value),
            unit=unit,
            source=_SYNTH_SOURCE,
            is_canonical=True,
            is_synthetic=True,
        )


def _wearable_to_sleep_record(wd: WearableDay):
    """Return a SleepRecord when sleep data is present, else None."""
    from app.models.health import SleepRecord

    if wd.total_sleep_seconds is None and wd.sleep_efficiency is None:
        return None
    return SleepRecord(
        user_id=wd.user_id,
        date=wd.date,
        efficiency=wd.sleep_efficiency,
        total_sleep_seconds=wd.total_sleep_seconds,
        deep_sleep_seconds=wd.deep_sleep_seconds,
        rem_sleep_seconds=wd.rem_sleep_seconds,
        light_sleep_seconds=wd.light_sleep_seconds,
        hrv_average=wd.hrv_average,
        resting_hr=wd.resting_hr,
        readiness_score=wd.readiness_score,
        bedtime_start=wd.bedtime_start,
        bedtime_end=wd.bedtime_end,
        is_synthetic=True,
    )


def _wearable_to_activity_record(wd: WearableDay):
    """Return an ActivityRecord (steps are always produced even when
    zero; an empty steps day is a signal, not missing data)."""
    from app.models.health import ActivityRecord

    return ActivityRecord(
        user_id=wd.user_id,
        date=wd.date,
        steps=wd.steps,
        active_calories=wd.active_calories,
        workout_type=wd.workout_type,
        workout_duration_seconds=wd.workout_duration_seconds,
        source=_SYNTH_SOURCE,
        is_synthetic=True,
    )


async def _write_wearables(
    db: "AsyncSession", wearables: list[WearableDay]
) -> dict[str, int]:
    """Add WearableDay rows to the session. Caller owns ``commit``."""
    counts = {"sleep_records": 0, "activity_records": 0, "health_metric_records": 0}
    for wd in wearables:
        sleep = _wearable_to_sleep_record(wd)
        if sleep is not None:
            db.add(sleep)
            counts["sleep_records"] += 1

        activity = _wearable_to_activity_record(wd)
        db.add(activity)
        counts["activity_records"] += 1

        for metric_row in _wearable_to_health_metric_rows(wd):
            db.add(metric_row)
            counts["health_metric_records"] += 1

        # Steps also surfaces as a HealthMetricRecord so downstream
        # builders that read the store see a canonical row.
        if wd.steps is not None:
            from app.models.health import HealthMetricRecord

            db.add(
                HealthMetricRecord(
                    user_id=wd.user_id,
                    date=wd.date,
                    metric_type="steps",
                    value=float(wd.steps),
                    unit="count",
                    source=_SYNTH_SOURCE,
                    is_canonical=True,
                    is_synthetic=True,
                )
            )
            counts["health_metric_records"] += 1
    # Flush so downstream meal FK inserts see the rows. (A flush is
    # cheaper than a full commit and respects the caller's outer
    # transaction.)
    await db.flush()
    return counts


async def _write_meals(
    db: "AsyncSession", meals: list[_SynthMeal]
) -> dict[str, int]:
    """Add MealRecord + FoodItemRecord pairs. Caller owns ``commit``."""
    from app.models.meal import FoodItemRecord, MealRecord

    counts = {"meal_records": 0, "food_item_records": 0}
    for meal in meals:
        m = MealRecord(
            user_id=meal.user_id,
            date=meal.date,
            meal_type=meal.meal_type,
            source=_SYNTH_SOURCE,
            created_at=meal.created_at,
            is_synthetic=True,
        )
        db.add(m)
        await db.flush()  # need m.id before inserting the food item
        counts["meal_records"] += 1
        item = meal.item
        db.add(
            FoodItemRecord(
                meal_id=m.id,
                name=item["name"],
                serving_size=item["serving_size"],
                serving_count=1.0,
                calories=item["calories"],
                protein=item["protein"],
                carbs=item["carbs"],
                fat=item["fat"],
                quality=item["quality"],
                data_source="ai_estimate",
                confidence=1.0,
                is_synthetic=True,
            )
        )
        counts["food_item_records"] += 1
    return counts


# ─────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────


async def generate_cohort(
    db: "AsyncSession",
    n_users: int,
    days: int | None = None,
    seed: int | None = None,
    generator: str | None = None,
) -> "CohortManifest":
    """Generate ``n_users`` synth users, write them, return the manifest.

    Non-negotiable side effects:

    - Every row written has ``is_synthetic=True``.
    - Every written date column is a ``YYYY-MM-DD`` string.
    - Does not call ``db.commit()``; the caller wraps this in
      ``async with db.begin()`` (or the scheduler job does).

    Raises ``ValueError`` on unknown ``generator`` and on negative
    ``n_users`` (the demographics generator enforces the latter; this
    function catches it and re-raises with the orchestrator context).
    """
    # Import the public CohortManifest here, not at module top, to keep
    # the synth factory boundary-clean: factory.py may not import from
    # ``ml.api`` at module load because ``ml.api`` itself wires lazily
    # back into ``ml.synth.factory``. (Avoids a circular import chain
    # at cold boot if the ml.api module-level resolves CohortManifest.)
    from ml.api import CohortManifest
    from ml.config import get_ml_settings

    settings = get_ml_settings()
    resolved_days = days if days is not None else settings.synth_default_days
    resolved_generator = (generator or settings.synth_default_generator).lower()
    biometric_miss = (
        settings.synth_biometric_missingness_low,
        settings.synth_biometric_missingness_high,
    )
    manual_miss = (
        settings.synth_manual_log_missingness_low,
        settings.synth_manual_log_missingness_high,
    )
    adversarial_fraction = settings.synth_adversarial_fraction

    if resolved_generator not in ("parametric", "gan"):
        raise ValueError(
            f"generator must be 'parametric' or 'gan', got {resolved_generator!r}"
        )
    if resolved_days < 1:
        raise ValueError(f"days must be >= 1, got {resolved_days}")

    demographics = generate_demographics(n_users=n_users, seed=seed)

    # Cohort window: today is the end; start is ``days`` days earlier
    # (inclusive). Using date.today() keeps synth data time-current so
    # it lands inside the feature-refresh window downstream.
    today = date.today()
    start = today - timedelta(days=resolved_days - 1)

    if resolved_generator == "gan":
        # wearables_gan raises ImportError when extras are not installed;
        # propagate unchanged so the API caller can surface the hint.
        from ml.synth.wearables_gan import generate_wearables_gan

        wearables = generate_wearables_gan(
            demographics=demographics,
            days=resolved_days,
            start_date=start,
            seed=seed,
            biometric_missingness=biometric_miss,
        )
    else:
        wearables = generate_wearables(
            demographics=demographics,
            days=resolved_days,
            start_date=start,
            seed=seed,
            biometric_missingness=biometric_miss,
        )

    meals = _generate_meals(
        demographics=demographics,
        days=resolved_days,
        start_date=start,
        seed=seed,
        manual_log_missingness=manual_miss,
    )

    await _write_wearables(db, wearables)
    await _write_meals(db, meals)

    # Compose the manifest first so the run_id stamped on the DB row is
    # exactly what the caller sees returned (same uuid, no copies).
    run_id = uuid.uuid4().hex
    manifest = CohortManifest(
        run_id=run_id,
        seed=seed,
        generator=resolved_generator,
        n_users=n_users,
        user_ids=[d.user_id for d in demographics],
        days=resolved_days,
        start_date=start.isoformat(),
        end_date=today.isoformat(),
        created_at=datetime.now(timezone.utc).isoformat(),
        adversarial_fraction=adversarial_fraction,
    )
    await _write_manifest(db, manifest)
    return manifest


async def _write_manifest(db: "AsyncSession", manifest: "CohortManifest") -> None:
    """Persist the manifest to ``ml_synth_runs`` in the caller's txn.

    Same session as the raw-table writes so the audit row and the
    ``is_synthetic=True`` rows land together; a rollback takes both.
    Caller owns ``commit``.
    """
    import json as _json

    from app.models.ml_synth import MLSynthRun

    db.add(
        MLSynthRun(
            run_id=manifest.run_id,
            seed=manifest.seed,
            generator=manifest.generator,
            n_users=manifest.n_users,
            days=manifest.days,
            start_date=manifest.start_date,
            end_date=manifest.end_date,
            created_at=manifest.created_at,
            adversarial_fraction=manifest.adversarial_fraction,
            user_ids_json=_json.dumps(manifest.user_ids),
        )
    )
    await db.flush()


__all__ = ["generate_cohort"]
