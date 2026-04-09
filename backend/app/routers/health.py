from datetime import datetime, date, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.database import get_db
from app.models.health import SleepRecord
from app.schemas.health import DashboardResponse, MetricResponse, RecoveryResponse, CoachInsightResponse
from app.services.claude import ClaudeClient
from app.services.oura_sync import sync_user_data

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/trends")
async def get_trends(range: int = 7, db: AsyncSession = Depends(get_db)):
    """Historical health metric trends for a given number of days.

    Returns arrays of values, dates, baselines, and personal ranges per metric.
    """
    start_date = (date.today() - timedelta(days=range)).isoformat()

    result = await db.execute(
        select(SleepRecord)
        .where(SleepRecord.user_id == "default", SleepRecord.date >= start_date)
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


@router.post("/sync/oura")
async def sync_oura(db: AsyncSession = Depends(get_db)):
    """Pull latest data from Oura API and store in DB."""
    return await sync_user_data(db, "default")


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    """Dashboard data — uses real Oura data if available, falls back to mock."""

    # Try to get real data from DB
    result = await db.execute(
        select(SleepRecord)
        .where(SleepRecord.user_id == "default")
        .order_by(desc(SleepRecord.date))
        .limit(7)
    )
    records = list(result.scalars().all())

    # Determine greeting
    hour = datetime.now().hour
    time_of_day = "morning" if 5 <= hour < 12 else "afternoon" if 12 <= hour < 17 else "evening" if 17 <= hour < 22 else "night"

    if records:
        # REAL DATA from Oura
        latest = records[0]

        # Sleep efficiency
        efficiency = latest.efficiency or 0
        total_sleep_secs = latest.total_sleep_seconds or 0
        hours = total_sleep_secs // 3600
        mins = (total_sleep_secs % 3600) // 60

        # Resting HR
        rhr = latest.resting_hr or 0

        # Readiness
        readiness = latest.readiness_score or 0
        readiness_level = "High" if readiness >= 67 else "Moderate" if readiness >= 34 else "Low"
        readiness_desc = {
            "High": "Good for hard training today",
            "Moderate": "Keep it easy today",
            "Low": "Your body needs rest today",
        }.get(readiness_level, "")

        # Compute 7-day average for trend
        avg_efficiency = sum(r.efficiency or 0 for r in records) / len(records) if records else 0
        efficiency_trend = "positive" if efficiency > avg_efficiency else "neutral" if efficiency == avg_efficiency else "negative"

        avg_rhr = sum(r.resting_hr or 0 for r in records if r.resting_hr) / max(1, sum(1 for r in records if r.resting_hr))
        rhr_diff = avg_rhr - rhr
        rhr_trend = "positive" if rhr_diff > 1 else "negative" if rhr_diff < -1 else "neutral"
        rhr_subtitle = f"{'Down' if rhr_diff > 0 else 'Up'} {abs(int(rhr_diff))} bpm vs avg" if abs(rhr_diff) >= 1 else "Stable this week"

        # Generate real coaching insight
        health_data = {
            "sleep_efficiency": f"{int(efficiency)}%",
            "sleep_duration": f"{hours}h {mins}m",
            "resting_hr": f"{int(rhr)} bpm",
            "readiness": readiness_level,
            "readiness_score": readiness,
        }

        try:
            claude = ClaudeClient()
            insight_text = claude.generate_insight(health_data, user_goals=["Lose weight", "Build muscle"])
        except Exception:
            insight_text = f"Your sleep efficiency was {int(efficiency)}% with {hours}h {mins}m of total sleep. Readiness is {readiness_level.lower()}."

        metrics = [
            MetricResponse(
                category="sleepEfficiency",
                label="Sleep Efficiency",
                value=str(int(efficiency)),
                unit="%",
                subtitle=f"{hours}h {mins}m total",
                trend=efficiency_trend,
            ),
            MetricResponse(
                category="restingHR",
                label="Resting HR",
                value=str(int(rhr)),
                unit="bpm",
                subtitle=rhr_subtitle,
                trend=rhr_trend,
            ),
            MetricResponse(
                category="consistency",
                label="Consistency",
                value=f"{len(records)}/7",
                unit="days",
                subtitle="Data from Oura",
                trend="positive" if len(records) >= 5 else "neutral",
            ),
        ]

        return DashboardResponse(
            greeting=f"Good {time_of_day}, Brock",
            date=datetime.now().strftime("%A, %B %-d"),
            metrics=metrics,
            recovery=RecoveryResponse(level=readiness_level, description=readiness_desc),
            coach_insight=CoachInsightResponse(
                message=insight_text,
                timestamp=datetime.now().isoformat(),
            ),
            last_synced=latest.synced_at.isoformat() if latest.synced_at else None,
        )

    else:
        # MOCK DATA fallback (no Oura data synced yet)
        return DashboardResponse(
            greeting=f"Good {time_of_day}, Brock",
            date=datetime.now().strftime("%A, %B %-d"),
            metrics=[
                MetricResponse(category="sleepEfficiency", label="Sleep Efficiency", value="91", unit="%", subtitle="7h 12m total", trend="positive"),
                MetricResponse(category="hrv", label="HRV Status", value="68", unit="ms", subtitle="↑ 14% vs baseline", trend="positive"),
                MetricResponse(category="restingHR", label="Resting HR", value="58", unit="bpm", subtitle="Stable this week", trend="neutral"),
                MetricResponse(category="consistency", label="Consistency", value="5/7", unit="days", subtitle="On track this week", trend="positive"),
            ],
            recovery=RecoveryResponse(level="High", description="Good for intensity today"),
            coach_insight=CoachInsightResponse(
                message="Connect your Oura Ring to see real coaching insights based on your actual sleep and recovery data.",
                timestamp=datetime.now().isoformat(),
            ),
            last_synced=None,
        )
