"""Feature builders: pull upstream rows, compute per-feature values.

Every builder is a **batch** function. Given one user and a date range, it
returns every feature it owns across every date in the range. This is
dramatically cheaper than per-(date, feature) queries when you are
materializing 30 days x 60 features per user every night.

Orchestration lives in ``store.materialize_for_user``. That function calls
each builder, merges the results into a single wide DataFrame, runs the
derived builder on top, emits the data-quality masks, and upserts to
``ml_feature_values`` in bulk.

All heavy imports (pandas, numpy) happen at function entry. Never at module
top level. See ``backend/ml/__init__.py`` and ``tests/ml/test_cold_boot.py``
for why.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

if TYPE_CHECKING:
    import pandas as pd
    from sqlalchemy.ext.asyncio import AsyncSession


# Canonical biometric metric types in HealthMetricRecord. Kept as a constant
# so builders and tests can reference the same keys.
BIOMETRIC_METRIC_TYPES: tuple[str, ...] = (
    "hrv",
    "resting_hr",
    "sleep_efficiency",
    "sleep_duration",  # note: stored as seconds in HealthMetricRecord; converted below
    "readiness_score",
)


# Mapping of feature_key -> which HealthMetricRecord.metric_type to pull.
# Some features need post-processing (e.g., seconds -> minutes).
@dataclass(frozen=True)
class _MetricSpec:
    metric_type: str
    scale: float = 1.0  # multiplier applied to the stored value


_BIOMETRIC_SOURCE: dict[str, _MetricSpec] = {
    "hrv": _MetricSpec("hrv"),
    "resting_hr": _MetricSpec("resting_hr"),
    "sleep_efficiency": _MetricSpec("sleep_efficiency"),
    "sleep_duration_minutes": _MetricSpec("sleep_duration", scale=1.0 / 60.0),  # sec->min
    "readiness_score": _MetricSpec("readiness_score"),
}


@dataclass
class MaterializedValue:
    """One row destined for the ``ml_feature_values`` table.

    ``user_id`` is not carried on this struct because the orchestrator always
    knows which user it is materializing; it sets it when upserting.
    """

    feature_key: str
    feature_date: str  # YYYY-MM-DD
    value: float | None
    is_observed: bool
    imputed_by: str | None = None
    feature_version: str = "1.0.0"
    source_row_ids: tuple[int, ...] = field(default_factory=tuple)

    def compute_source_hash(self) -> str:
        """SHA-1 of the source row ids; cheap cache invalidation key."""
        if not self.source_row_ids:
            return ""
        payload = json.dumps(sorted(self.source_row_ids)).encode()
        # SHA-1 chosen for cache key (non-cryptographic). usedforsecurity=False
        # tells hashlib it's a checksum; Semgrep's rule doesn't recognize the
        # arg so we suppress here.
        # nosemgrep: python.lang.security.insecure-hash-algorithms.insecure-hash-algorithm-sha1
        return hashlib.sha1(payload, usedforsecurity=False).hexdigest()


# ─────────────────────────────────────────────────────────────────────────
# Date helpers
# ─────────────────────────────────────────────────────────────────────────


def _daterange(start: date, end: date) -> list[date]:
    """Inclusive list of dates from start through end."""
    if end < start:
        return []
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def _date_to_str(d: date) -> str:
    return d.isoformat()


# ─────────────────────────────────────────────────────────────────────────
# Biometric raw builder
# ─────────────────────────────────────────────────────────────────────────


async def build_biometric_raw(
    db: "AsyncSession",
    user_id: str,
    start: date,
    end: date,
) -> list[MaterializedValue]:
    """Pull canonical biometric rows and emit one MaterializedValue per
    (date, feature_key). Dates with no data emit an is_observed=False row
    with value=None; the orchestrator decides whether to impute.

    ``deep_sleep_minutes`` and ``rem_sleep_minutes`` fall back to
    ``SleepRecord`` because those are stored there (HealthMetricRecord does
    not carry the stage breakdown yet).
    """
    from app.models.health import HealthMetricRecord, SleepRecord

    start_s, end_s = _date_to_str(start), _date_to_str(end)
    metric_types = [spec.metric_type for spec in _BIOMETRIC_SOURCE.values()]

    # One query gets every canonical biometric row for the window.
    result = await db.execute(
        select(HealthMetricRecord).where(
            HealthMetricRecord.user_id == user_id,
            HealthMetricRecord.is_canonical.is_(True),
            HealthMetricRecord.metric_type.in_(metric_types),
            HealthMetricRecord.date >= start_s,
            HealthMetricRecord.date <= end_s,
        )
    )
    rows = list(result.scalars().all())

    # Group by (date, metric_type) so we can scale and emit cleanly.
    by_date_metric: dict[tuple[str, str], tuple[float, int]] = {}
    for row in rows:
        by_date_metric[(row.date, row.metric_type)] = (row.value, row.id)

    # SleepRecord fallback for deep/rem minutes.
    sleep_result = await db.execute(
        select(SleepRecord).where(
            SleepRecord.user_id == user_id,
            SleepRecord.date >= start_s,
            SleepRecord.date <= end_s,
        )
    )
    sleep_rows = {r.date: r for r in sleep_result.scalars().all()}

    out: list[MaterializedValue] = []
    for d in _daterange(start, end):
        ds = _date_to_str(d)

        # Each feature in _BIOMETRIC_SOURCE.
        for feature_key, spec in _BIOMETRIC_SOURCE.items():
            key = (ds, spec.metric_type)
            if key in by_date_metric:
                raw, row_id = by_date_metric[key]
                out.append(
                    MaterializedValue(
                        feature_key=feature_key,
                        feature_date=ds,
                        value=raw * spec.scale,
                        is_observed=True,
                        source_row_ids=(row_id,),
                    )
                )
            else:
                out.append(
                    MaterializedValue(
                        feature_key=feature_key,
                        feature_date=ds,
                        value=None,
                        is_observed=False,
                    )
                )

        # deep_sleep_minutes + rem_sleep_minutes from SleepRecord.
        sleep = sleep_rows.get(ds)
        for feature_key, attr in (
            ("deep_sleep_minutes", "deep_sleep_seconds"),
            ("rem_sleep_minutes", "rem_sleep_seconds"),
        ):
            if sleep is not None and getattr(sleep, attr) is not None:
                out.append(
                    MaterializedValue(
                        feature_key=feature_key,
                        feature_date=ds,
                        value=getattr(sleep, attr) / 60.0,
                        is_observed=True,
                        source_row_ids=(sleep.id,),
                    )
                )
            else:
                out.append(
                    MaterializedValue(
                        feature_key=feature_key,
                        feature_date=ds,
                        value=None,
                        is_observed=False,
                    )
                )

    return out


# ─────────────────────────────────────────────────────────────────────────
# Activity builder
# ─────────────────────────────────────────────────────────────────────────


async def build_activity(
    db: "AsyncSession",
    user_id: str,
    start: date,
    end: date,
) -> list[MaterializedValue]:
    """Steps, active calories, workout counts and durations.

    Uses ActivityRecord as the source of truth. Multiple rows per day
    (e.g., multiple workouts) are aggregated.

    Queries a widened window (60 days back from ``start``) so the
    ``days_since_last_workout`` feature can find workouts older than the
    materialization window. Daily aggregates still use only rows in
    ``[start, end]``.
    """
    from app.models.health import ActivityRecord

    # 60-day lookback is enough for "days since last workout" to stay
    # meaningful even if a user took a ~2 month break.
    ACTIVITY_LOOKBACK_DAYS = 60
    wide_start_s = _date_to_str(start - timedelta(days=ACTIVITY_LOOKBACK_DAYS))
    start_s, end_s = _date_to_str(start), _date_to_str(end)

    result = await db.execute(
        select(ActivityRecord).where(
            ActivityRecord.user_id == user_id,
            ActivityRecord.date >= wide_start_s,
            ActivityRecord.date <= end_s,
        )
    )
    rows = list(result.scalars().all())

    # Aggregate by date. Note: we only aggregate rows that fall in the
    # requested window. Rows outside [start, end] are kept in `rows` only
    # to power the days_since_last_workout lookback.
    agg: dict[
        str,
        dict[str, Any],
    ] = {}
    for row in rows:
        if row.date < start_s or row.date > end_s:
            continue
        bucket = agg.setdefault(
            row.date,
            {
                "steps": 0,
                "active_calories": 0,
                "workout_count": 0,
                "workout_duration_seconds": 0,
                "row_ids": [],
                "had_any": False,
            },
        )
        bucket["had_any"] = True
        bucket["row_ids"].append(row.id)
        if row.steps is not None:
            bucket["steps"] = max(bucket["steps"], row.steps)  # HealthKit aggregate vs per-workout
        if row.active_calories is not None:
            bucket["active_calories"] += row.active_calories
        if row.workout_type:
            bucket["workout_count"] += 1
            if row.workout_duration_seconds is not None:
                bucket["workout_duration_seconds"] += row.workout_duration_seconds

    # Find last workout on or before each date for days_since_last_workout.
    workout_dates: list[str] = sorted(
        {r.date for r in rows if r.workout_type is not None}
    )

    out: list[MaterializedValue] = []
    for d in _daterange(start, end):
        ds = _date_to_str(d)
        bucket = agg.get(ds)

        if bucket and bucket["had_any"]:
            source_ids = tuple(bucket["row_ids"])
            out.extend([
                MaterializedValue("steps", ds, float(bucket["steps"]), True, source_row_ids=source_ids),
                MaterializedValue("active_calories", ds, float(bucket["active_calories"]), True, source_row_ids=source_ids),
                MaterializedValue("workout_count", ds, float(bucket["workout_count"]), True, source_row_ids=source_ids),
                MaterializedValue(
                    "workout_duration_sum_minutes",
                    ds,
                    bucket["workout_duration_seconds"] / 60.0,
                    True,
                    source_row_ids=source_ids,
                ),
            ])
        else:
            for key in ("steps", "active_calories", "workout_count", "workout_duration_sum_minutes"):
                out.append(MaterializedValue(key, ds, None, False))

        # days_since_last_workout — look at workout_dates up to and including this day.
        prior_workouts = [wd for wd in workout_dates if wd <= ds]
        if prior_workouts:
            last = prior_workouts[-1]
            delta = (d - date.fromisoformat(last)).days
            out.append(MaterializedValue("days_since_last_workout", ds, float(delta), True))
        else:
            # No workouts yet. Mark not observed rather than guessing infinity.
            out.append(MaterializedValue("days_since_last_workout", ds, None, False))

        # training_load_7d — exp-weighted sum of workout minutes over last 7 days.
        # alpha = 0.3 approximates a half-life of ~2 days, biases toward recent training.
        alpha = 0.3
        load = 0.0
        any_minutes = False
        for i, dd in enumerate(reversed(_daterange(d - timedelta(days=6), d))):
            b = agg.get(_date_to_str(dd))
            if b and b["had_any"]:
                minutes = b["workout_duration_seconds"] / 60.0
                load += minutes * ((1 - alpha) ** i)
                any_minutes = True
        if any_minutes:
            out.append(MaterializedValue("training_load_7d", ds, load, True))
        else:
            out.append(MaterializedValue("training_load_7d", ds, 0.0, True, imputed_by="none"))

    return out


# ─────────────────────────────────────────────────────────────────────────
# Nutrition builder
# ─────────────────────────────────────────────────────────────────────────


async def build_nutrition(
    db: "AsyncSession",
    user_id: str,
    start: date,
    end: date,
) -> list[MaterializedValue]:
    """Aggregate calories and macros per day from logged meals."""
    from app.models.meal import FoodItemRecord, MealRecord

    start_s, end_s = _date_to_str(start), _date_to_str(end)

    # Pull meals for the window.
    meals_result = await db.execute(
        select(MealRecord).where(
            MealRecord.user_id == user_id,
            MealRecord.date >= start_s,
            MealRecord.date <= end_s,
        )
    )
    meals = list(meals_result.scalars().all())
    if not meals:
        out: list[MaterializedValue] = []
        for d in _daterange(start, end):
            ds = _date_to_str(d)
            for key in ("calories", "protein_g", "carbs_g", "fat_g", "meal_count", "dinner_hour"):
                out.append(MaterializedValue(key, ds, None, False))
        return out

    # Index meals by id so we can find their foods quickly.
    meal_ids = [m.id for m in meals]
    foods_result = await db.execute(
        select(FoodItemRecord).where(FoodItemRecord.meal_id.in_(meal_ids))
    )
    foods = list(foods_result.scalars().all())
    foods_by_meal: dict[int, list[FoodItemRecord]] = {}
    for f in foods:
        foods_by_meal.setdefault(f.meal_id, []).append(f)

    # Aggregate per date.
    per_date: dict[str, dict[str, Any]] = {}
    for m in meals:
        bucket = per_date.setdefault(
            m.date,
            {
                "calories": 0.0,
                "protein_g": 0.0,
                "carbs_g": 0.0,
                "fat_g": 0.0,
                "meal_count": 0,
                "row_ids": [],
                "dinner_hours": [],  # created_at.hour for each dinner MealRecord
            },
        )
        bucket["meal_count"] += 1
        bucket["row_ids"].append(m.id)
        # dinner_hour feature: track log-hour of any meal tagged 'dinner'.
        # Uses created_at rather than an eat-time field (none exists yet).
        # When multiple dinners are logged, the latest wins (see output stage).
        if (m.meal_type or "").lower() == "dinner" and m.created_at is not None:
            bucket["dinner_hours"].append(m.created_at.hour)
        for f in foods_by_meal.get(m.id, []):
            # serving_count scales the nutrition. Guard against None.
            servings = f.serving_count if f.serving_count is not None else 1.0
            bucket["calories"] += (f.calories or 0) * servings
            bucket["protein_g"] += (f.protein or 0.0) * servings
            bucket["carbs_g"] += (f.carbs or 0.0) * servings
            bucket["fat_g"] += (f.fat or 0.0) * servings

    out = []
    for d in _daterange(start, end):
        ds = _date_to_str(d)
        bucket = per_date.get(ds)
        if bucket:
            src = tuple(bucket["row_ids"])
            out.extend([
                MaterializedValue("calories", ds, bucket["calories"], True, source_row_ids=src),
                MaterializedValue("protein_g", ds, bucket["protein_g"], True, source_row_ids=src),
                MaterializedValue("carbs_g", ds, bucket["carbs_g"], True, source_row_ids=src),
                MaterializedValue("fat_g", ds, bucket["fat_g"], True, source_row_ids=src),
                MaterializedValue("meal_count", ds, float(bucket["meal_count"]), True, source_row_ids=src),
            ])
            dinner_hours = bucket["dinner_hours"]
            if dinner_hours:
                # Latest-logged dinner wins when multiple dinners on same date.
                out.append(
                    MaterializedValue(
                        "dinner_hour", ds, float(max(dinner_hours)), True, source_row_ids=src
                    )
                )
            else:
                # Meals logged but none tagged 'dinner'. is_observed=False
                # because we treat missing dinner as absence of the signal,
                # matching the missing-as-informative convention elsewhere.
                out.append(MaterializedValue("dinner_hour", ds, None, False))
        else:
            for key in ("calories", "protein_g", "carbs_g", "fat_g", "meal_count", "dinner_hour"):
                out.append(MaterializedValue(key, ds, None, False))

    return out


# ─────────────────────────────────────────────────────────────────────────
# Contextual builder (calendar + engagement)
# ─────────────────────────────────────────────────────────────────────────


async def build_contextual(
    db: "AsyncSession",
    user_id: str,
    start: date,
    end: date,
) -> list[MaterializedValue]:
    """Weekday, weekend flag, days-since-install. Pure calendar, no ML deps."""
    from app.models.health import HealthMetricRecord

    # Earliest HealthMetricRecord.date acts as the install proxy. Cheap, no
    # dependency on any auth/user table details.
    earliest_result = await db.execute(
        select(HealthMetricRecord.date)
        .where(HealthMetricRecord.user_id == user_id)
        .order_by(HealthMetricRecord.date.asc())
        .limit(1)
    )
    earliest_row = earliest_result.scalar_one_or_none()
    earliest: date | None = (
        date.fromisoformat(earliest_row) if earliest_row else None
    )

    out: list[MaterializedValue] = []
    for d in _daterange(start, end):
        ds = _date_to_str(d)
        weekday = d.weekday()
        out.append(MaterializedValue("weekday", ds, float(weekday), True))
        out.append(MaterializedValue("is_weekend", ds, 1.0 if weekday >= 5 else 0.0, True))

        if earliest is not None:
            delta = max(0, (d - earliest).days)
            out.append(MaterializedValue("days_since_install", ds, float(delta), True))
        else:
            out.append(MaterializedValue("days_since_install", ds, None, False))

    return out


# ─────────────────────────────────────────────────────────────────────────
# Data-quality builder (completeness masks)
# ─────────────────────────────────────────────────────────────────────────


async def build_quality(
    db: "AsyncSession",
    user_id: str,
    start: date,
    end: date,
) -> list[MaterializedValue]:
    """Share of the trailing 14 days with at least one observed row, per domain.

    Uses raw existence checks (not feature-level) so the mask reflects the
    underlying data availability, not whether the feature happened to compute
    on any particular day.
    """
    from app.models.health import ActivityRecord, HealthMetricRecord
    from app.models.meal import MealRecord

    # Collect distinct dates with observations per domain, for the whole
    # [start - 13d, end] span so the trailing-14 mask is defined on every
    # requested date.
    lookback_start = start - timedelta(days=13)
    lookback_start_s = _date_to_str(lookback_start)
    end_s = _date_to_str(end)

    bio_dates_result = await db.execute(
        select(HealthMetricRecord.date)
        .where(
            HealthMetricRecord.user_id == user_id,
            HealthMetricRecord.is_canonical.is_(True),
            HealthMetricRecord.date >= lookback_start_s,
            HealthMetricRecord.date <= end_s,
        )
        .distinct()
    )
    bio_dates = {r for r in bio_dates_result.scalars().all()}

    activity_dates_result = await db.execute(
        select(ActivityRecord.date)
        .where(
            ActivityRecord.user_id == user_id,
            ActivityRecord.date >= lookback_start_s,
            ActivityRecord.date <= end_s,
        )
        .distinct()
    )
    activity_dates = {r for r in activity_dates_result.scalars().all()}

    meal_dates_result = await db.execute(
        select(MealRecord.date)
        .where(
            MealRecord.user_id == user_id,
            MealRecord.date >= lookback_start_s,
            MealRecord.date <= end_s,
        )
        .distinct()
    )
    meal_dates = {r for r in meal_dates_result.scalars().all()}

    out: list[MaterializedValue] = []
    for d in _daterange(start, end):
        ds = _date_to_str(d)
        window = {_date_to_str(d - timedelta(days=i)) for i in range(14)}
        out.append(
            MaterializedValue(
                "completeness_14d.biometric",
                ds,
                len(window & bio_dates) / 14.0,
                True,
            )
        )
        out.append(
            MaterializedValue(
                "completeness_14d.activity",
                ds,
                len(window & activity_dates) / 14.0,
                True,
            )
        )
        out.append(
            MaterializedValue(
                "completeness_14d.nutrition",
                ds,
                len(window & meal_dates) / 14.0,
                True,
            )
        )

    return out


# ─────────────────────────────────────────────────────────────────────────
# Derived builder (rolling stats, deltas, z-scores)
# ─────────────────────────────────────────────────────────────────────────


def build_derived(frame: "pd.DataFrame", requested_keys: set[str]) -> list[MaterializedValue]:
    """Compute derived features on top of an already-materialized raw frame.

    ``frame`` is a wide pandas DataFrame indexed by ``feature_date`` with one
    column per raw feature. ``requested_keys`` is the catalog subset of
    derived feature keys the caller wants. Unknown keys are silently skipped
    (the store handles gaps separately).

    Returns a list of MaterializedValue rows, one per (date, derived-key).
    """
    import numpy as np
    import pandas as pd  # noqa: F401  -- indexing via attribute only

    out: list[MaterializedValue] = []

    # Group requested derived keys by their raw parent so we compute each
    # transform once per raw column.
    by_parent: dict[str, list[str]] = {}
    for key in requested_keys:
        if "." not in key:
            continue
        parent, _, suffix = key.rpartition(".")
        if parent in frame.columns:
            by_parent.setdefault(parent, []).append(key)

    for parent, keys in by_parent.items():
        series = frame[parent]  # may have NaN for unobserved days

        for key in keys:
            suffix = key.rsplit(".", 1)[-1]

            if suffix == "7d_rolling_mean":
                computed = series.rolling(window=7, min_periods=3).mean()
            elif suffix == "28d_rolling_mean":
                computed = series.rolling(window=28, min_periods=7).mean()
            elif suffix == "7d_rolling_std":
                computed = series.rolling(window=7, min_periods=3).std()
            elif suffix == "7d_delta":
                computed = series - series.shift(7)
            elif suffix == "z_score_28d":
                mean_28 = series.rolling(window=28, min_periods=7).mean()
                std_28 = series.rolling(window=28, min_periods=7).std()
                computed = (series - mean_28) / std_28
            else:
                # Unknown suffix — defensive default.
                continue

            for idx, val in computed.items():
                feature_date = str(idx)
                if val is None or (isinstance(val, float) and (np.isnan(val) or np.isinf(val))):
                    out.append(MaterializedValue(key, feature_date, None, False))
                else:
                    out.append(
                        MaterializedValue(key, feature_date, float(val), True)
                    )

    return out
