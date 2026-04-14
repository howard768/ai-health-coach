"""Feature catalog for the Signal Engine.

This is the declarative registry of every feature the store knows how to
materialize. Each entry names the builder responsible, the version of that
builder, and any upstream features it depends on.

The catalog is the source of truth. The DB ``ml_feature_catalog`` table is
synced from here on every nightly run so downstream services can list
available features without importing ``backend.ml.*`` directly (which would
violate the import boundary).

Versions are per-feature semver. Bump when the math changes; old rows in
``ml_feature_values`` with a different version stay around until a cleanup
job sweeps them out.

Phase 1 ships ~60 features. Phase 2+ will add catch22, dinner_hour,
eating_window, late_eating_flag, etc.
"""

from __future__ import annotations

from dataclasses import dataclass


# Current catalog version. Bump when adding / removing / renaming features,
# not when just tweaking a single feature's version field.
CATALOG_VERSION = "1.0.0"


@dataclass(frozen=True)
class FeatureSpec:
    """One row in the catalog.

    ``builder_module`` is a dotted path to the builder function. The worker
    that materializes a day's features uses this to dispatch to the right
    code. Kept as a string (not a callable) so the catalog can be imported
    cheaply without pulling in pandas / scipy at module load.
    """

    key: str
    category: str  # biometric_raw | biometric_derived | activity | nutrition | contextual | data_quality
    domain: str  # sleep | heart | activity | nutrition | engagement | time
    description: str
    unit: str
    builder_module: str  # e.g. "ml.features.builders:biometric_raw"
    version: str  # semver of this feature's math
    requires: tuple[str, ...] = ()  # feature keys this derives from


# ─────────────────────────────────────────────────────────────────────────
# Biometric raw (pulled straight from reconciled HealthMetricRecord +
# SleepRecord fallback). These are the foundation every other biometric
# feature derives from.
# ─────────────────────────────────────────────────────────────────────────
BIOMETRIC_RAW = [
    FeatureSpec(
        key="hrv",
        category="biometric_raw",
        domain="heart",
        description="Heart rate variability (SDNN), milliseconds. Canonical per day.",
        unit="ms",
        builder_module="ml.features.builders:build_biometric_raw",
        version="1.0.0",
    ),
    FeatureSpec(
        key="resting_hr",
        category="biometric_raw",
        domain="heart",
        description="Resting heart rate, beats per minute. Canonical per day.",
        unit="bpm",
        builder_module="ml.features.builders:build_biometric_raw",
        version="1.0.0",
    ),
    FeatureSpec(
        key="sleep_efficiency",
        category="biometric_raw",
        domain="sleep",
        description="Share of time in bed actually asleep, 0-100.",
        unit="percent",
        builder_module="ml.features.builders:build_biometric_raw",
        version="1.0.0",
    ),
    FeatureSpec(
        key="sleep_duration_minutes",
        category="biometric_raw",
        domain="sleep",
        description="Total sleep time for the night, minutes.",
        unit="minutes",
        builder_module="ml.features.builders:build_biometric_raw",
        version="1.0.0",
    ),
    FeatureSpec(
        key="deep_sleep_minutes",
        category="biometric_raw",
        domain="sleep",
        description="Minutes in deep (N3) sleep.",
        unit="minutes",
        builder_module="ml.features.builders:build_biometric_raw",
        version="1.0.0",
    ),
    FeatureSpec(
        key="rem_sleep_minutes",
        category="biometric_raw",
        domain="sleep",
        description="Minutes in REM sleep.",
        unit="minutes",
        builder_module="ml.features.builders:build_biometric_raw",
        version="1.0.0",
    ),
    FeatureSpec(
        key="readiness_score",
        category="biometric_raw",
        domain="heart",
        description="Oura readiness score, 0-100. Proprietary; not merged across sources.",
        unit="score",
        builder_module="ml.features.builders:build_biometric_raw",
        version="1.0.0",
    ),
]


# ─────────────────────────────────────────────────────────────────────────
# Biometric derived. For each raw biometric we compute a small set of
# common transforms. Generated programmatically to keep the declarations
# short and avoid copy-paste drift.
# ─────────────────────────────────────────────────────────────────────────
_DERIVED_SUFFIXES = [
    ("7d_rolling_mean", "Trailing 7-day mean (window ends on the feature date).", ""),
    ("28d_rolling_mean", "Trailing 28-day mean (personal baseline).", ""),
    ("7d_rolling_std", "Trailing 7-day standard deviation.", ""),
    ("7d_delta", "Difference from this value 7 days ago.", ""),
    ("z_score_28d", "Standardized deviation from personal trailing 28-day mean.", "sigma"),
]


def _derived_specs() -> list[FeatureSpec]:
    specs: list[FeatureSpec] = []
    for raw in BIOMETRIC_RAW:
        for suffix, desc, unit_override in _DERIVED_SUFFIXES:
            specs.append(
                FeatureSpec(
                    key=f"{raw.key}.{suffix}",
                    category="biometric_derived",
                    domain=raw.domain,
                    description=f"{raw.description} {desc}".strip(),
                    unit=unit_override or raw.unit,
                    builder_module="ml.features.builders:build_derived",
                    version="1.0.0",
                    requires=(raw.key,),
                )
            )
    return specs


BIOMETRIC_DERIVED = _derived_specs()


# ─────────────────────────────────────────────────────────────────────────
# Activity.
# ─────────────────────────────────────────────────────────────────────────
ACTIVITY = [
    FeatureSpec(
        key="steps",
        category="activity",
        domain="activity",
        description="Daily step count. Canonical per day.",
        unit="steps",
        builder_module="ml.features.builders:build_activity",
        version="1.0.0",
    ),
    FeatureSpec(
        key="active_calories",
        category="activity",
        domain="activity",
        description="Active energy burned, kcal.",
        unit="kcal",
        builder_module="ml.features.builders:build_activity",
        version="1.0.0",
    ),
    FeatureSpec(
        key="workout_count",
        category="activity",
        domain="activity",
        description="Number of discrete workouts completed today.",
        unit="count",
        builder_module="ml.features.builders:build_activity",
        version="1.0.0",
    ),
    FeatureSpec(
        key="workout_duration_sum_minutes",
        category="activity",
        domain="activity",
        description="Total workout duration, minutes.",
        unit="minutes",
        builder_module="ml.features.builders:build_activity",
        version="1.0.0",
    ),
    FeatureSpec(
        key="days_since_last_workout",
        category="activity",
        domain="activity",
        description="Days since the last recorded workout. 0 if today has one.",
        unit="days",
        builder_module="ml.features.builders:build_activity",
        version="1.0.0",
    ),
    FeatureSpec(
        key="training_load_7d",
        category="activity",
        domain="activity",
        description="Exponentially weighted sum of workout minutes over trailing 7d.",
        unit="minutes",
        builder_module="ml.features.builders:build_activity",
        version="1.0.0",
    ),
]


# ─────────────────────────────────────────────────────────────────────────
# Nutrition.
# ─────────────────────────────────────────────────────────────────────────
NUTRITION = [
    FeatureSpec(
        key="calories",
        category="nutrition",
        domain="nutrition",
        description="Total daily calories from logged meals.",
        unit="kcal",
        builder_module="ml.features.builders:build_nutrition",
        version="1.0.0",
    ),
    FeatureSpec(
        key="protein_g",
        category="nutrition",
        domain="nutrition",
        description="Total daily protein, grams.",
        unit="g",
        builder_module="ml.features.builders:build_nutrition",
        version="1.0.0",
    ),
    FeatureSpec(
        key="carbs_g",
        category="nutrition",
        domain="nutrition",
        description="Total daily carbohydrates, grams.",
        unit="g",
        builder_module="ml.features.builders:build_nutrition",
        version="1.0.0",
    ),
    FeatureSpec(
        key="fat_g",
        category="nutrition",
        domain="nutrition",
        description="Total daily fat, grams.",
        unit="g",
        builder_module="ml.features.builders:build_nutrition",
        version="1.0.0",
    ),
    FeatureSpec(
        key="meal_count",
        category="nutrition",
        domain="nutrition",
        description="Number of meals logged today.",
        unit="count",
        builder_module="ml.features.builders:build_nutrition",
        version="1.0.0",
    ),
    FeatureSpec(
        key="protein_g.7d_rolling_mean",
        category="nutrition",
        domain="nutrition",
        description="Trailing 7-day mean of daily protein grams.",
        unit="g",
        builder_module="ml.features.builders:build_derived",
        version="1.0.0",
        requires=("protein_g",),
    ),
]


# ─────────────────────────────────────────────────────────────────────────
# Contextual (no health data needed, pure calendar / engagement).
# ─────────────────────────────────────────────────────────────────────────
CONTEXTUAL = [
    FeatureSpec(
        key="weekday",
        category="contextual",
        domain="time",
        description="Day of week, 0=Monday...6=Sunday.",
        unit="dow",
        builder_module="ml.features.builders:build_contextual",
        version="1.0.0",
    ),
    FeatureSpec(
        key="is_weekend",
        category="contextual",
        domain="time",
        description="1 if Saturday or Sunday, else 0.",
        unit="bool",
        builder_module="ml.features.builders:build_contextual",
        version="1.0.0",
    ),
    FeatureSpec(
        key="days_since_install",
        category="contextual",
        domain="engagement",
        description="Days since the earliest HealthMetricRecord or ChatMessage for this user.",
        unit="days",
        builder_module="ml.features.builders:build_contextual",
        version="1.0.0",
    ),
]


# ─────────────────────────────────────────────────────────────────────────
# Data quality masks. These ride alongside the real features as a
# completeness signal; every downstream model must read them and decide
# how to treat imputed values.
# ─────────────────────────────────────────────────────────────────────────
DATA_QUALITY = [
    FeatureSpec(
        key="completeness_14d.biometric",
        category="data_quality",
        domain="heart",
        description="Share of last 14 days with at least one observed biometric row.",
        unit="ratio",
        builder_module="ml.features.builders:build_quality",
        version="1.0.0",
    ),
    FeatureSpec(
        key="completeness_14d.activity",
        category="data_quality",
        domain="activity",
        description="Share of last 14 days with at least one observed activity row.",
        unit="ratio",
        builder_module="ml.features.builders:build_quality",
        version="1.0.0",
    ),
    FeatureSpec(
        key="completeness_14d.nutrition",
        category="data_quality",
        domain="nutrition",
        description="Share of last 14 days with at least one meal logged.",
        unit="ratio",
        builder_module="ml.features.builders:build_quality",
        version="1.0.0",
    ),
]


# Master catalog. Order matters only for deterministic iteration; materialization
# reorders by `requires` via topological sort anyway.
CATALOG: tuple[FeatureSpec, ...] = tuple(
    [*BIOMETRIC_RAW, *BIOMETRIC_DERIVED, *ACTIVITY, *NUTRITION, *CONTEXTUAL, *DATA_QUALITY]
)


def iter_catalog() -> tuple[FeatureSpec, ...]:
    """Return every feature spec in the catalog. Stable order."""
    return CATALOG


def get_spec(feature_key: str) -> FeatureSpec | None:
    """Look up a single feature spec by key. Returns None if unknown."""
    for spec in CATALOG:
        if spec.key == feature_key:
            return spec
    return None


def specs_by_category(category: str) -> tuple[FeatureSpec, ...]:
    """All specs in a given category, stable order."""
    return tuple(s for s in CATALOG if s.category == category)


def topologically_ordered() -> tuple[FeatureSpec, ...]:
    """Return the catalog ordered so every feature appears after its dependencies.

    The materialization loop uses this so derived features can assume their
    raw inputs are already in the working frame. Stable within-level ordering
    is by insertion order in the CATALOG constant above.
    """
    remaining = list(CATALOG)
    ordered: list[FeatureSpec] = []
    placed: set[str] = set()

    # Simple fixed-point: keep sweeping until no new features can be placed.
    # Cycles would break this; the catalog is a DAG by construction.
    while remaining:
        progress = False
        for spec in list(remaining):
            if all(req in placed for req in spec.requires):
                ordered.append(spec)
                placed.add(spec.key)
                remaining.remove(spec)
                progress = True
        if not progress:
            # Cycle or missing dependency. Surface a loud error rather than
            # silently dropping features.
            missing = {
                req for spec in remaining for req in spec.requires if req not in placed
            }
            raise RuntimeError(
                f"Catalog has cycle or missing dependencies: {sorted(missing)}; "
                f"unplaced: {[s.key for s in remaining]}"
            )

    return tuple(ordered)
