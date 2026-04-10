from datetime import datetime, date, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.api.deps import CurrentUser
from app.database import get_db
from app.models.health import SleepRecord
from app.models.user import User
from app.schemas.health import DashboardResponse, MetricResponse, RecoveryResponse, CoachInsightResponse
from app.services.claude import ClaudeClient
from app.services.oura_sync import sync_user_data
from app.services.health_data import get_latest_health_data


def _first_name_of(user: User) -> str:
    """Get the user's first name for greetings, or empty string if no name."""
    if user.name:
        return user.name.split()[0]
    return ""

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/trends")
async def get_trends(
    current_user: CurrentUser,
    range: int = 7,
    db: AsyncSession = Depends(get_db),
):
    """Historical health metric trends for a given number of days.

    Returns arrays of values, dates, baselines, and personal ranges per metric.
    """
    start_date = (date.today() - timedelta(days=range)).isoformat()

    result = await db.execute(
        select(SleepRecord)
        .where(SleepRecord.user_id == current_user.apple_user_id, SleepRecord.date >= start_date)
        .order_by(SleepRecord.date)
    )
    records = list(result.scalars().all())

    if not records:
        return {"range_days": range, "metrics": {}}

    def build_metric(values):
        clean = [v for v in values if v is not None]
        if not clean:
            return {"values": [], "dates": [], "baseline": 0, "personal_min": 0, "personal_max": 0, "personal_average": 0}
        return {
            "values": clean,
            "baseline": round(sum(clean) / len(clean), 1),
            "personal_min": round(min(clean), 1),
            "personal_max": round(max(clean), 1),
            "personal_average": round(sum(clean) / len(clean), 1),
        }

    dates = [r.date for r in records]
    sleep_eff = build_metric([r.efficiency for r in records])
    sleep_eff["dates"] = dates
    resting_hr = build_metric([r.resting_hr for r in records])
    resting_hr["dates"] = dates
    readiness = build_metric([r.readiness_score for r in records])
    readiness["dates"] = dates
    hrv = build_metric([r.hrv_average for r in records])
    hrv["dates"] = dates

    return {
        "range_days": range,
        "metrics": {
            "sleep_efficiency": sleep_eff,
            "resting_hr": resting_hr,
            "readiness": readiness,
            "hrv": hrv,
        },
    }


@router.post("/health/apple-health")
async def sync_apple_health(
    metrics: list[dict],
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Batch sync HealthKit data from iOS device.

    Each metric: {date, metric_type, value, unit, source}
    Writes to HealthMetricRecord for reconciliation.
    """
    from app.models.health import HealthMetricRecord

    # Cap at 1000 metrics per request to prevent DoS (P1-5 fix)
    if len(metrics) > 1000:
        raise HTTPException(status_code=413, detail="Max 1000 metrics per request")

    user_id = current_user.apple_user_id
    saved = 0
    for m in metrics:
        # Check for existing record (dedup by user+date+metric+source)
        existing = await db.execute(
            select(HealthMetricRecord).where(
                HealthMetricRecord.user_id == user_id,
                HealthMetricRecord.date == m.get("date", ""),
                HealthMetricRecord.metric_type == m.get("metric_type", ""),
                HealthMetricRecord.source == m.get("source", "apple_health"),
            )
        )
        if existing.scalar_one_or_none():
            continue

        record = HealthMetricRecord(
            user_id=user_id,
            date=m.get("date", ""),
            metric_type=m.get("metric_type", ""),
            value=float(m.get("value", 0)),
            unit=m.get("unit", ""),
            source=m.get("source", "apple_health"),
        )
        db.add(record)
        saved += 1

    if saved:
        await db.commit()
        # Run reconciliation for today
        from app.services.data_reconciliation import reconcile_day
        today = datetime.now().strftime("%Y-%m-%d")
        await reconcile_day(db, user_id, today)

    return {"status": "ok", "records_saved": saved}


@router.post("/sync/oura")
async def sync_oura(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Pull latest data from Oura API and store in DB."""
    return await sync_user_data(db, current_user.apple_user_id)


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Dashboard data — reads from reconciled multi-source health data."""

    hour = datetime.now().hour
    time_of_day = "morning" if 5 <= hour < 12 else "afternoon" if 12 <= hour < 17 else "evening" if 17 <= hour < 22 else "night"

    first_name = _first_name_of(current_user)
    greeting = f"Good {time_of_day}, {first_name}" if first_name else f"Good {time_of_day}"

    # Load reconciled data (multi-source: Oura + Apple Health + Garmin + Peloton)
    health_data = await get_latest_health_data(db, current_user.apple_user_id)

    if not health_data:
        return DashboardResponse(
            greeting=greeting,
            date=datetime.now().strftime("%A, %B %-d"),
            metrics=[],
            recovery=RecoveryResponse(level="High", description="Connect a data source to start"),
            coach_insight=CoachInsightResponse(
                message="Connect your Oura Ring or Apple Health to see coaching insights based on your real data.",
                timestamp=datetime.now().isoformat(),
            ),
            last_synced=None,
        )

    # Extract values from reconciled data
    efficiency = health_data.get("sleep_efficiency", 0)
    sleep_hours = health_data.get("sleep_duration_hours", 0)
    hours = int(sleep_hours)
    mins = int((sleep_hours - hours) * 60)
    rhr = health_data.get("resting_hr", 0)
    hrv = health_data.get("hrv_average", 0)
    readiness = health_data.get("readiness_score", 0)
    steps = health_data.get("steps", 0)
    baseline_rhr = health_data.get("baseline_rhr", rhr)
    baseline_hrv = health_data.get("baseline_hrv", hrv)
    sources = health_data.get("data_sources", {})

    readiness_level = "High" if readiness >= 67 else "Moderate" if readiness >= 34 else "Low"
    readiness_desc = {
        "High": "Good for hard training today",
        "Moderate": "Keep it easy today",
        "Low": "Your body needs rest today",
    }.get(readiness_level, "")

    # Trends
    eff_trend = "positive" if efficiency > 75 else "negative" if efficiency < 60 else "neutral"
    rhr_diff = baseline_rhr - rhr
    rhr_trend = "positive" if rhr_diff > 1 else "negative" if rhr_diff < -1 else "neutral"
    rhr_subtitle = f"{'Down' if rhr_diff > 0 else 'Up'} {abs(int(rhr_diff))} bpm vs avg" if abs(rhr_diff) >= 1 else "Stable"

    # Source attribution for subtitle
    sleep_source = sources.get("sleep_efficiency", "")
    source_label = f" via {sleep_source.replace('_', ' ').title()}" if sleep_source else ""

    # Generate coaching insight
    insight_context = {
        "sleep_efficiency": f"{int(efficiency)}%",
        "sleep_duration": f"{hours}h {mins}m",
        "resting_hr": f"{int(rhr)} bpm",
        "readiness": readiness_level,
        "readiness_score": readiness,
    }
    try:
        import asyncio
        claude = ClaudeClient()
        insight_text = await asyncio.to_thread(
            claude.generate_insight, insight_context, ["Lose weight", "Build muscle"]
        )
    except Exception:
        insight_text = f"Your sleep efficiency was {int(efficiency)}% with {hours}h {mins}m of total sleep. Readiness is {readiness_level.lower()}."

    metrics = [
        MetricResponse(
            category="sleepEfficiency", label="Sleep Efficiency",
            value=str(int(efficiency)), unit="%",
            subtitle=f"{hours}h {mins}m total{source_label}", trend=eff_trend,
        ),
    ]
    if hrv:
        hrv_diff = hrv - baseline_hrv
        hrv_pct = int(abs(hrv_diff) / max(baseline_hrv, 1) * 100)
        hrv_trend = "positive" if hrv_diff > 0 else "negative" if hrv_diff < 0 else "neutral"
        hrv_subtitle = f"{'Up' if hrv_diff > 0 else 'Down'} {hrv_pct}% vs baseline" if hrv_pct > 2 else "Stable"
        metrics.append(MetricResponse(
            category="hrv", label="HRV Status",
            value=str(int(hrv)), unit="ms",
            subtitle=hrv_subtitle, trend=hrv_trend,
        ))
    if rhr:
        metrics.append(MetricResponse(
            category="restingHR", label="Resting HR",
            value=str(int(rhr)), unit="bpm",
            subtitle=rhr_subtitle, trend=rhr_trend,
        ))
    if steps:
        metrics.append(MetricResponse(
            category="consistency", label="Steps",
            value=f"{int(steps):,}", unit="steps",
            subtitle=f"via {sources.get('steps', 'device').replace('_', ' ').title()}", trend="positive" if steps > 5000 else "neutral",
        ))

    return DashboardResponse(
        greeting=greeting,
        date=datetime.now().strftime("%A, %B %-d"),
        metrics=metrics,
        recovery=RecoveryResponse(level=readiness_level, description=readiness_desc),
        coach_insight=CoachInsightResponse(
            message=insight_text,
            timestamp=datetime.now().isoformat(),
        ),
        last_synced=datetime.now().isoformat(),
    )
