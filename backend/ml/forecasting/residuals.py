"""Short-horizon per-metric forecasting.

Ensemble of two estimators (seasonal-naive + Prophet), 50/50 blend, 95%
prediction interval. Writes to ``ml_forecasts``. Read by anomaly detection
in ``ml.forecasting.anomaly`` to residualize new observations.

Prophet adds a non-trivial import cost (~1.5s on cold boot) and spins up
cmdstan. Both facts are fine because this module is ONLY imported lazily
from ``ml.api`` function bodies; the cold-boot test guards the invariant.

See ``~/.claude/plans/golden-floating-creek.md`` Phase 2 for the design.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import delete

if TYPE_CHECKING:
    import pandas as pd
    from sqlalchemy.ext.asyncio import AsyncSession


MODEL_VERSION = "ensemble-1.0.0"
MIN_HISTORY_DAYS = 90
DEFAULT_HORIZON_DAYS = 7

# Headline biometric metrics we forecast. These are the ones the coach
# surfaces and the ones anomaly detection actually acts on.
FORECAST_METRICS: tuple[str, ...] = (
    "hrv",
    "resting_hr",
    "sleep_efficiency",
    "readiness_score",
    "steps",
)


@dataclass
class ForecastPoint:
    """A single (target_date, y_hat, y_hat_low, y_hat_high) row."""

    target_date: str
    y_hat: float | None
    y_hat_low: float | None
    y_hat_high: float | None


@dataclass
class ForecastOutput:
    """Output of ``forecast_for_series``."""

    metric_key: str
    made_on: str
    model_version: str
    points: list[ForecastPoint]


# ─────────────────────────────────────────────────────────────────────────
# Component forecasts
# ─────────────────────────────────────────────────────────────────────────


def _seasonal_naive_forecast(
    series: "pd.Series",
    made_on: date,
    horizon_days: int,
) -> list[ForecastPoint]:
    """``y_hat[t+h] = y[t+h - 7]`` (same weekday last week).

    Cheap, deterministic, and surprisingly strong on weekly-periodic data.
    Returns NaN-valued points when the lookback day is missing.
    """
    import numpy as np

    points: list[ForecastPoint] = []
    for h in range(1, horizon_days + 1):
        target = made_on + timedelta(days=h)
        # Reach back exactly 7 days from the target to find the same weekday.
        lookback = target - timedelta(days=7)
        lookback_s = lookback.isoformat()
        if lookback_s in series.index and np.isfinite(series.loc[lookback_s]):
            y = float(series.loc[lookback_s])
            points.append(
                ForecastPoint(
                    target_date=target.isoformat(),
                    y_hat=y,
                    y_hat_low=None,
                    y_hat_high=None,
                )
            )
        else:
            points.append(
                ForecastPoint(
                    target_date=target.isoformat(),
                    y_hat=None,
                    y_hat_low=None,
                    y_hat_high=None,
                )
            )
    return points


def _prophet_forecast(
    series: "pd.Series",
    made_on: date,
    horizon_days: int,
) -> list[ForecastPoint]:
    """Prophet with daily + weekly seasonality, no yearly.

    Returns NaN points if Prophet fails (too little data, numerical issues,
    cmdstan startup failure). That way the ensemble can still fall back on
    the seasonal-naive forecast without taking down the whole job.
    """
    import numpy as np
    import pandas as pd

    valid = series.dropna()
    if valid.shape[0] < MIN_HISTORY_DAYS:
        return [
            ForecastPoint(
                target_date=(made_on + timedelta(days=h)).isoformat(),
                y_hat=None,
                y_hat_low=None,
                y_hat_high=None,
            )
            for h in range(1, horizon_days + 1)
        ]

    try:
        from prophet import Prophet  # type: ignore[import-not-found]
    except Exception:  # cmdstan missing, import fail, etc.
        return [
            ForecastPoint(
                target_date=(made_on + timedelta(days=h)).isoformat(),
                y_hat=None,
                y_hat_low=None,
                y_hat_high=None,
            )
            for h in range(1, horizon_days + 1)
        ]

    prophet_df = pd.DataFrame(
        {"ds": pd.to_datetime(valid.index), "y": valid.astype(float).values}
    )

    try:
        model = Prophet(
            daily_seasonality=False,
            weekly_seasonality=True,
            yearly_seasonality=False,
            interval_width=0.95,
        )
        # Silence prophet's stdout chatter during fit.
        import logging

        logging.getLogger("prophet").setLevel(logging.ERROR)
        logging.getLogger("cmdstanpy").setLevel(logging.ERROR)
        model.fit(prophet_df)
        future = pd.DataFrame(
            {
                "ds": [
                    pd.Timestamp(made_on + timedelta(days=h))
                    for h in range(1, horizon_days + 1)
                ]
            }
        )
        forecast = model.predict(future)
    except Exception:
        return [
            ForecastPoint(
                target_date=(made_on + timedelta(days=h)).isoformat(),
                y_hat=None,
                y_hat_low=None,
                y_hat_high=None,
            )
            for h in range(1, horizon_days + 1)
        ]

    points: list[ForecastPoint] = []
    for _, row in forecast.iterrows():
        target = row["ds"].date().isoformat()
        y_hat = float(row["yhat"]) if np.isfinite(row["yhat"]) else None
        y_lo = float(row["yhat_lower"]) if np.isfinite(row["yhat_lower"]) else None
        y_hi = float(row["yhat_upper"]) if np.isfinite(row["yhat_upper"]) else None
        points.append(
            ForecastPoint(
                target_date=target,
                y_hat=y_hat,
                y_hat_low=y_lo,
                y_hat_high=y_hi,
            )
        )
    return points


def forecast_for_series(
    series: "pd.Series",
    metric_key: str,
    made_on: date,
    horizon_days: int = DEFAULT_HORIZON_DAYS,
    use_prophet: bool = True,
) -> ForecastOutput:
    """Ensemble forecast: 50/50 blend of seasonal-naive and Prophet.

    Falls back to whichever estimator produced a finite value if one NaN'd.
    The ``use_prophet`` flag is used by tests to isolate the naive path.
    """
    import numpy as np

    naive_pts = _seasonal_naive_forecast(series, made_on, horizon_days)
    prophet_pts: list[ForecastPoint] = []
    if use_prophet:
        prophet_pts = _prophet_forecast(series, made_on, horizon_days)

    merged: list[ForecastPoint] = []
    for i, naive in enumerate(naive_pts):
        prophet = prophet_pts[i] if i < len(prophet_pts) else None

        y_hats = [
            p.y_hat
            for p in (naive, prophet)
            if p is not None and p.y_hat is not None and np.isfinite(p.y_hat)
        ]
        if not y_hats:
            merged.append(
                ForecastPoint(
                    target_date=naive.target_date,
                    y_hat=None,
                    y_hat_low=None,
                    y_hat_high=None,
                )
            )
            continue

        y_hat = float(np.mean(y_hats))

        # Use Prophet's interval when available; fall back to ±2·σ around
        # the naive point using the series' residual std as an approximation.
        if prophet and prophet.y_hat_low is not None and prophet.y_hat_high is not None:
            y_lo = prophet.y_hat_low
            y_hi = prophet.y_hat_high
        else:
            sigma = float(np.nanstd(series.dropna(), ddof=1)) if series.dropna().shape[0] > 1 else 0.0
            y_lo = y_hat - 1.96 * sigma if sigma > 0 else None
            y_hi = y_hat + 1.96 * sigma if sigma > 0 else None

        merged.append(
            ForecastPoint(
                target_date=naive.target_date,
                y_hat=y_hat,
                y_hat_low=y_lo,
                y_hat_high=y_hi,
            )
        )

    return ForecastOutput(
        metric_key=metric_key,
        made_on=made_on.isoformat(),
        model_version=MODEL_VERSION,
        points=merged,
    )


# ─────────────────────────────────────────────────────────────────────────
# User-level orchestrator + persistence
# ─────────────────────────────────────────────────────────────────────────


async def compute_forecasts_for_user(
    db: "AsyncSession",
    user_id: str,
    made_on: date,
    horizon_days: int = DEFAULT_HORIZON_DAYS,
    use_prophet: bool = True,
) -> dict[str, ForecastOutput]:
    """Forecast every headline metric for the given made_on date.

    Writes rows to ``ml_forecasts``. Caller owns the transaction. Returns
    a dict keyed by metric for inspection in tests and downstream code.
    """
    from ml.features.store import get_feature_frame

    start = made_on - timedelta(days=MIN_HISTORY_DAYS * 2)
    frame = await get_feature_frame(
        db,
        user_id,
        feature_keys=list(FORECAST_METRICS),
        start=start,
        end=made_on,
        include_imputed=False,
    )

    outputs: dict[str, ForecastOutput] = {}
    to_persist: list[tuple[str, ForecastOutput]] = []
    for metric in FORECAST_METRICS:
        if metric not in frame.columns:
            continue
        output = forecast_for_series(
            frame[metric],
            metric_key=metric,
            made_on=made_on,
            horizon_days=horizon_days,
            use_prophet=use_prophet,
        )
        outputs[metric] = output
        to_persist.append((metric, output))

    await _upsert_forecasts(db, user_id, made_on, to_persist)
    return outputs


async def _upsert_forecasts(
    db: "AsyncSession",
    user_id: str,
    made_on: date,
    entries: list[tuple[str, ForecastOutput]],
) -> None:
    from app.core.time import utcnow_naive
    from app.models.ml_baselines import MLForecast

    if not entries:
        return
    made_on_s = made_on.isoformat()

    metric_keys = {metric for metric, _ in entries}
    # Clear any existing (user, metric, made_on) rows with our model version
    # so rerunning the job the same day replaces rather than duplicates.
    await db.execute(
        delete(MLForecast).where(
            MLForecast.user_id == user_id,
            MLForecast.metric_key.in_(metric_keys),
            MLForecast.made_on == made_on_s,
            MLForecast.model_version == MODEL_VERSION,
        )
    )

    now = utcnow_naive()
    for metric, output in entries:
        for point in output.points:
            db.add(
                MLForecast(
                    user_id=user_id,
                    metric_key=metric,
                    target_date=point.target_date,
                    made_on=made_on_s,
                    y_hat=point.y_hat,
                    y_hat_low=point.y_hat_low,
                    y_hat_high=point.y_hat_high,
                    model_version=MODEL_VERSION,
                    computed_at=now,
                )
            )
