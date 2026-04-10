from datetime import datetime, date, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func

from app.api.deps import CurrentUser
from app.database import get_db
from app.models.health import SleepRecord
from app.models.meal import MealRecord, FoodItemRecord
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


@router.get("/trends/patterns")
async def get_trend_patterns(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Cross-domain pattern insights derived from sleep and nutrition data over 30 days."""
    thirty_days_ago = (date.today() - timedelta(days=30)).isoformat()

    sleep_result = await db.execute(
        select(SleepRecord)
        .where(SleepRecord.user_id == current_user.apple_user_id, SleepRecord.date >= thirty_days_ago)
        .order_by(SleepRecord.date)
    )
    sleep_records = list(sleep_result.scalars().all())

    if not sleep_records:
        return {"patterns": []}

    days_total = len(sleep_records)

    # Load daily nutrition totals for the same window
    nutrition_result = await db.execute(
        select(
            MealRecord.date,
            func.sum(FoodItemRecord.protein).label("total_protein"),
            func.sum(FoodItemRecord.calories).label("total_calories"),
        )
        .join(FoodItemRecord, FoodItemRecord.meal_id == MealRecord.id)
        .where(MealRecord.user_id == current_user.apple_user_id, MealRecord.date >= thirty_days_ago)
        .group_by(MealRecord.date)
    )
    nutrition_by_date = {
        row.date: {"protein": float(row.total_protein or 0), "calories": float(row.total_calories or 0)}
        for row in nutrition_result
    }

    patterns = []

    # Pattern 1: High sleep efficiency nights correlate with higher HRV
    high_eff = [r for r in sleep_records if r.efficiency is not None and r.efficiency >= 85 and r.hrv_average]
    low_eff = [r for r in sleep_records if r.efficiency is not None and r.efficiency < 75 and r.hrv_average]
    if len(high_eff) >= 3 and len(low_eff) >= 2:
        avg_high_hrv = sum(r.hrv_average for r in high_eff) / len(high_eff)
        avg_low_hrv = sum(r.hrv_average for r in low_eff) / len(low_eff)
        if avg_high_hrv > avg_low_hrv * 1.04:
            confidence = min(0.95, 0.55 + len(high_eff) / days_total)
            patterns.append({
                "pattern_text": (
                    f"Your HRV averages {int(avg_high_hrv)}ms on nights with >85% sleep efficiency, "
                    f"vs {int(avg_low_hrv)}ms on poor nights."
                ),
                "confidence": round(confidence, 2),
                "days_matched": len(high_eff),
                "days_total": days_total,
            })

    # Pattern 2: High protein intake correlates with better readiness
    if nutrition_by_date:
        paired = [
            (nutrition_by_date[r.date]["protein"], r.readiness_score)
            for r in sleep_records
            if r.date in nutrition_by_date and r.readiness_score is not None
        ]
        if len(paired) >= 4:
            high_p = [(p, r) for p, r in paired if p >= 120]
            low_p = [(p, r) for p, r in paired if p < 80]
            if len(high_p) >= 2 and len(low_p) >= 2:
                avg_r_high = sum(r for _, r in high_p) / len(high_p)
                avg_r_low = sum(r for _, r in low_p) / len(low_p)
                if avg_r_high > avg_r_low * 1.04:
                    confidence = min(0.90, 0.48 + len(high_p) / days_total)
                    patterns.append({
                        "pattern_text": (
                            f"On days you hit 120g+ protein, your readiness score averages "
                            f"{int(avg_r_high)} vs {int(avg_r_low)} on lower-protein days."
                        ),
                        "confidence": round(confidence, 2),
                        "days_matched": len(high_p),
                        "days_total": days_total,
                    })

    # Pattern 3: Resting HR trend vs period baseline (fitness improvement signal)
    rhr_records = [r for r in sleep_records if r.resting_hr is not None]
    if len(rhr_records) >= 7:
        half = len(rhr_records) // 2
        avg_first = sum(r.resting_hr for r in rhr_records[:half]) / half
        avg_second = sum(r.resting_hr for r in rhr_records[half:]) / (len(rhr_records) - half)
        if avg_second < avg_first * 0.97:
            drop = round(avg_first - avg_second, 1)
            patterns.append({
                "pattern_text": (
                    f"Your resting heart rate dropped {drop} bpm over the last 30 days — "
                    "a sign your cardiovascular fitness is improving."
                ),
                "confidence": 0.88,
                "days_matched": len(rhr_records),
                "days_total": days_total,
            })

    # Return top 3 by confidence
    patterns.sort(key=lambda p: p["confidence"], reverse=True)
    return {"patterns": patterns[:3]}


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
    rhr_delta = (
        f"{'Down' if rhr_diff > 0 else 'Up'} {abs(int(rhr_diff))} bpm vs avg"
        if abs(rhr_diff) >= 1 else "Stable"
    )

    # Source attribution — pretty labels we reuse in every metric subtitle
    def _pretty_source(raw: str) -> str:
        return raw.replace("_", " ").title() if raw else ""

    sleep_source = _pretty_source(sources.get("sleep_efficiency", ""))
    rhr_source = _pretty_source(sources.get("resting_hr", ""))
    hrv_source = _pretty_source(sources.get("hrv", ""))
    steps_source = _pretty_source(sources.get("steps", "device"))

    def _with_source(primary: str, source: str) -> str:
        """Append ' · via Source' to a subtitle, skipping if source is empty."""
        if not source:
            return primary
        if not primary:
            return f"via {source}"
        return f"{primary} · via {source}"

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
            subtitle=_with_source(f"{hours}h {mins}m total", sleep_source), trend=eff_trend,
        ),
    ]
    if hrv:
        hrv_diff = hrv - baseline_hrv
        hrv_pct = int(abs(hrv_diff) / max(baseline_hrv, 1) * 100)
        hrv_trend = "positive" if hrv_diff > 0 else "negative" if hrv_diff < 0 else "neutral"
        hrv_delta = (
            f"{'Up' if hrv_diff > 0 else 'Down'} {hrv_pct}% vs baseline"
            if hrv_pct > 2 else "Stable"
        )
        metrics.append(MetricResponse(
            category="hrv", label="HRV Status",
            value=str(int(hrv)), unit="ms",
            subtitle=_with_source(hrv_delta, hrv_source), trend=hrv_trend,
        ))
    if rhr:
        metrics.append(MetricResponse(
            category="restingHR", label="Resting HR",
            value=str(int(rhr)), unit="bpm",
            subtitle=_with_source(rhr_delta, rhr_source), trend=rhr_trend,
        ))
    if steps:
        metrics.append(MetricResponse(
            category="consistency", label="Steps",
            value=f"{int(steps):,}", unit="steps",
            subtitle=f"via {steps_source}" if steps_source else "steps",
            trend="positive" if steps > 5000 else "neutral",
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
