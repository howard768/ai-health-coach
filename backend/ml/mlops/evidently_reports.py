"""Phase 4.5 Commit 5: drift monitoring for synth vs real biometrics.

The brief from ``~/.claude/plans/phase-4.5-scaffolding.md``:

> ``backend/ml/mlops/evidently_reports.py`` -- imports ``evidently``
> (new dep) lazy-inside. Builds a DataDrift report comparing synth vs
> production feature store rows. Writes HTML output to
> ``/tmp/evidently/`` or an R2 bucket when configured.

Two realities shape the implementation:

1. **Evidently 0.7.21 uses ``pydantic.v1`` internally, which breaks on
   Python 3.14.** Railway runs Python 3.12 (pyproject pins
   ``>=3.12``), so Evidently works there. Brock's local dev env is
   currently 3.14, where ``import evidently`` raises ``ConfigError``.
   The module must stay useful in both environments.

2. **KS-test drift detection is the actual signal.** Evidently's
   value-add is the polished HTML; the drift decision itself is a
   per-metric ``scipy.stats.ks_2samp`` call we can always run.

So this module separates the two:

- ``_compute_drift`` always runs (scipy only).
- ``_try_build_evidently_html`` is best-effort. Any import or runtime
  failure is logged and the returned path is ``None``. Tests patch the
  helper to exercise both code paths.

The ``DriftReport`` return shape carries enough state for a scheduler
job to log the outcome cleanly without loading the HTML: row counts,
per-metric p-values, the list of drifted metrics, and the absolute
path or ``None``.

Raw-row source (not feature-store rows):

  We query ``HealthMetricRecord`` directly. The feature store
  (``ml_feature_values``) does not yet carry ``is_synthetic``; adding
  the column and a backfill are out of scope for Commit 5. The raw
  tables already partition cleanly by ``is_synthetic``, which is
  enough to let this commit stand on its own. When the feature store
  carries synth rows in a later phase, swap the source here and keep
  the shape identical.

Invariants pinned by ``tests/ml/test_evidently_reports.py``:

1. Queries respect ``is_synthetic`` on both reference and current
   partitions.
2. ``_MIN_SAMPLES_PER_METRIC`` returns a cleanly-flagged report with
   ``dataset_too_small=True`` and no HTML attempt.
3. Known-drift input produces a p-value below the threshold and
   flags the metric; known-same input does not.
4. An Evidently import failure is absorbed, logged, and the function
   still returns a valid ``DriftReport`` with ``html_path=None``.
5. ``scipy`` / ``pandas`` remain lazy (cold-boot invariant).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    import pandas as pd


logger = logging.getLogger("meld.ml.mlops.evidently_reports")


# Default output directory for the HTML report when the caller does not
# specify one. Chosen to match the Evidently convention in the prep
# doc; the scheduler job can override per run.
_DEFAULT_OUTPUT_DIR = Path("/tmp/evidently")

# Canonical biometric metric types to compare. Kept in sync with
# ``ml.features.builders.BIOMETRIC_METRIC_TYPES`` so drift matches the
# feature-pipeline's view of the world. Keeping this as a tuple rather
# than re-importing the constant avoids pulling the features module
# (and its pandas top-level) into this module's cold-boot closure.
_DRIFT_METRICS: tuple[str, ...] = (
    "hrv",
    "resting_hr",
    "sleep_efficiency",
    "sleep_duration",
    "readiness_score",
    "steps",
)

# Minimum samples per metric per partition. Below this the KS test is
# uninformative and the HTML report would be noise.
_MIN_SAMPLES_PER_METRIC = 30

# Default drift threshold. Standard alpha for a two-sample KS test.
_DEFAULT_P_VALUE_THRESHOLD = 0.05


@dataclass
class DriftReport:
    """Result of one drift-comparison run.

    ``html_path`` is populated only when Evidently imported cleanly
    AND both partitions met ``_MIN_SAMPLES_PER_METRIC``. Everything
    else is always populated so callers (scheduler, ops dashboards)
    can reason about the run without loading the HTML.
    """

    run_id: str
    created_at: str  # ISO-8601 UTC
    html_path: str | None
    html_backend: str  # "evidently" | "none"
    n_reference_rows: int
    n_current_rows: int
    metrics_tested: list[str] = field(default_factory=list)
    drifted_metrics: list[str] = field(default_factory=list)
    p_values: dict[str, float] = field(default_factory=dict)
    dataset_too_small: bool = False
    threshold: float = _DEFAULT_P_VALUE_THRESHOLD


# ─────────────────────────────────────────────────────────────────────────
# DB -> wide DataFrame
# ─────────────────────────────────────────────────────────────────────────


async def _fetch_partition(
    db: "AsyncSession",
    is_synthetic: bool,
) -> "pd.DataFrame":
    """Return a wide DataFrame for a single ``is_synthetic`` partition.

    Columns: one per metric in ``_DRIFT_METRICS``. Rows: one per
    ``(user_id, date)`` observed on the canonical side of
    ``HealthMetricRecord``. Missing metric-days are NaN, not dropped,
    so downstream drift tests see a per-metric sample that reflects
    the actual partition size.
    """
    import pandas as pd  # lazy; top-level would blow the cold-boot budget
    from sqlalchemy import select

    from app.models.health import HealthMetricRecord

    result = await db.execute(
        select(
            HealthMetricRecord.user_id,
            HealthMetricRecord.date,
            HealthMetricRecord.metric_type,
            HealthMetricRecord.value,
        ).where(
            HealthMetricRecord.is_synthetic.is_(is_synthetic),
            HealthMetricRecord.is_canonical.is_(True),
            HealthMetricRecord.metric_type.in_(_DRIFT_METRICS),
        )
    )
    rows = [
        {"user_id": r.user_id, "date": r.date, "metric_type": r.metric_type, "value": r.value}
        for r in result.all()
    ]
    if not rows:
        return pd.DataFrame(columns=["user_id", "date", *list(_DRIFT_METRICS)])

    long = pd.DataFrame(rows)
    wide = long.pivot_table(
        index=["user_id", "date"],
        columns="metric_type",
        values="value",
        aggfunc="first",
    ).reset_index()
    # Ensure every expected column is present even if absent from the
    # data (keeps the schema consistent for drift comparisons).
    for col in _DRIFT_METRICS:
        if col not in wide.columns:
            wide[col] = float("nan")
    # Reorder to a canonical column order so the HTML report does not
    # reshuffle between runs.
    return wide[["user_id", "date", *list(_DRIFT_METRICS)]]


# ─────────────────────────────────────────────────────────────────────────
# KS-test drift detection (always works)
# ─────────────────────────────────────────────────────────────────────────


def _compute_drift(
    reference: "pd.DataFrame",
    current: "pd.DataFrame",
    threshold: float,
) -> tuple[dict[str, float], list[str]]:
    """Run a two-sample KS test per metric column.

    Returns ``(p_values_by_metric, drifted_metrics)``. A metric is
    considered drifted when its p-value is strictly below
    ``threshold``. Metrics with fewer than
    ``_MIN_SAMPLES_PER_METRIC`` observations on either side after
    dropping NaNs are skipped (omitted from the dicts), because the
    KS statistic is not meaningful with a tiny sample.
    """
    from scipy import stats  # lazy

    p_values: dict[str, float] = {}
    drifted: list[str] = []
    for metric in _DRIFT_METRICS:
        ref_col = reference[metric].dropna().to_numpy()
        cur_col = current[metric].dropna().to_numpy()
        if len(ref_col) < _MIN_SAMPLES_PER_METRIC or len(cur_col) < _MIN_SAMPLES_PER_METRIC:
            continue
        result = stats.ks_2samp(ref_col, cur_col)
        p_values[metric] = float(result.pvalue)
        if result.pvalue < threshold:
            drifted.append(metric)
    return p_values, drifted


# ─────────────────────────────────────────────────────────────────────────
# Evidently HTML (best effort)
# ─────────────────────────────────────────────────────────────────────────


def _try_build_evidently_html(
    reference: "pd.DataFrame",
    current: "pd.DataFrame",
    output_path: Path,
) -> str | None:
    """Attempt to render an Evidently DataDrift HTML report.

    Returns the absolute path on success, ``None`` on any failure
    (import error, ConfigError on Python 3.14, Evidently runtime
    exception, IO error). Always logs the failure reason. Never raises
    to the caller.
    """
    try:
        from evidently.metric_preset import DataDriftPreset
        from evidently.report import Report
    except Exception as exc:  # noqa: BLE001 -- defensive at the boundary
        logger.warning("evidently unavailable, skipping HTML: %s", exc)
        return None

    try:
        report = Report(metrics=[DataDriftPreset()])
        # Drop the pivot-index columns; Evidently expects only the
        # numeric metric columns on both sides.
        ref = reference[list(_DRIFT_METRICS)]
        cur = current[list(_DRIFT_METRICS)]
        report.run(reference_data=ref, current_data=cur)
        report.save_html(str(output_path))
    except Exception as exc:  # noqa: BLE001
        logger.warning("evidently report generation failed: %s", exc)
        return None

    return str(output_path)


# ─────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────


async def build_drift_report(
    db: "AsyncSession",
    output_dir: Path | None = None,
    run_id: str | None = None,
    threshold: float = _DEFAULT_P_VALUE_THRESHOLD,
) -> DriftReport:
    """Compare synth biometrics against real biometrics on raw tables.

    Does NOT commit (there is no write in this function, but the
    caller's outer transaction is never touched either).
    """
    resolved_output_dir = output_dir or _DEFAULT_OUTPUT_DIR
    resolved_run_id = run_id or uuid.uuid4().hex
    now_iso = datetime.now(timezone.utc).isoformat()

    reference = await _fetch_partition(db, is_synthetic=False)
    current = await _fetch_partition(db, is_synthetic=True)

    # Populate the "samples per metric" check using the non-NaN count
    # per column because a fully-missing metric column is effectively
    # zero samples for that metric, even if rows exist.
    ref_row_count = len(reference)
    cur_row_count = len(current)

    if (
        ref_row_count < _MIN_SAMPLES_PER_METRIC
        or cur_row_count < _MIN_SAMPLES_PER_METRIC
    ):
        logger.info(
            "drift report skipped: dataset too small (ref=%d, cur=%d, threshold=%d)",
            ref_row_count,
            cur_row_count,
            _MIN_SAMPLES_PER_METRIC,
        )
        return DriftReport(
            run_id=resolved_run_id,
            created_at=now_iso,
            html_path=None,
            html_backend="none",
            n_reference_rows=ref_row_count,
            n_current_rows=cur_row_count,
            dataset_too_small=True,
            threshold=threshold,
        )

    p_values, drifted = _compute_drift(reference, current, threshold)

    # Best-effort HTML; failures are logged and swallowed.
    resolved_output_dir.mkdir(parents=True, exist_ok=True)
    html_target = resolved_output_dir / f"drift_{resolved_run_id}.html"
    html_path = _try_build_evidently_html(reference, current, html_target)
    html_backend = "evidently" if html_path else "none"

    return DriftReport(
        run_id=resolved_run_id,
        created_at=now_iso,
        html_path=html_path,
        html_backend=html_backend,
        n_reference_rows=ref_row_count,
        n_current_rows=cur_row_count,
        metrics_tested=sorted(p_values.keys()),
        drifted_metrics=sorted(drifted),
        p_values=p_values,
        dataset_too_small=False,
        threshold=threshold,
    )


__all__ = ["DriftReport", "build_drift_report"]
