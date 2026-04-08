from datetime import datetime, date, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.database import get_db
from app.models.health import OuraToken, SleepRecord
from app.schemas.health import DashboardResponse, MetricResponse, RecoveryResponse, CoachInsightResponse
from app.services.oura import OuraClient
from app.services.claude import ClaudeClient

router = APIRouter(prefix="/api", tags=["health"])


@router.post("/sync/oura")
async def sync_oura(db: AsyncSession = Depends(get_db)):
    """Pull latest data from Oura API and store in DB."""
    # Get stored token
    result = await db.execute(
        select(OuraToken).order_by(desc(OuraToken.created_at)).limit(1)
    )
    token = result.scalar_one_or_none()
    if not token:
        return {"status": "error", "message": "No Oura token found. Connect your ring first."}

    client = OuraClient(access_token=token.access_token)

    # Pull last 7 days of sleep data
    start = date.today() - timedelta(days=7)
    end = date.today()

    try:
        sleep_data = await client.get_daily_sleep(start, end)
        readiness_data = await client.get_daily_readiness(start, end)
    except Exception as e:
        return {"status": "error", "message": f"Oura API error: {str(e)}"}

    # Store sleep records
    records_saved = 0
    for day in sleep_data.get("data", []):
        day_date = day.get("day", "")

        # Check if record already exists
        existing = await db.execute(
            select(SleepRecord).where(
                SleepRecord.user_id == "default",
                SleepRecord.date == day_date,
            )
        )
        if existing.scalar_one_or_none():
            continue

        # Find matching readiness score
        readiness_score = None
        for r in readiness_data.get("data", []):
            if r.get("day") == day_date:
                readiness_score = r.get("score")
                break

        contributors = day.get("contributors", {})
        # Extract bedtime start/end for personalized notification timing
        bedtime_start_raw = day.get("bedtime_start")  # ISO 8601 timestamp
        bedtime_end_raw = day.get("bedtime_end")
        bedtime_start = None
        bedtime_end = None
        if bedtime_start_raw:
            try:
                from datetime import datetime as dt
                bedtime_start = dt.fromisoformat(bedtime_start_raw.replace("Z", "+00:00")).strftime("%H:%M")
            except (ValueError, AttributeError):
                pass
        if bedtime_end_raw:
            try:
                from datetime import datetime as dt
                bedtime_end = dt.fromisoformat(bedtime_end_raw.replace("Z", "+00:00")).strftime("%H:%M")
            except (ValueError, AttributeError):
                pass

        record = SleepRecord(
            user_id="default",
            date=day_date,
            efficiency=contributors.get("efficiency"),
            total_sleep_seconds=day.get("total_sleep_duration"),
            deep_sleep_seconds=day.get("deep_sleep_duration"),
            rem_sleep_seconds=day.get("rem_sleep_duration"),
            light_sleep_seconds=day.get("light_sleep_duration"),
            hrv_average=None,  # HRV comes from a separate endpoint
            resting_hr=day.get("lowest_heart_rate"),
            readiness_score=readiness_score,
            bedtime_start=bedtime_start,
            bedtime_end=bedtime_end,
            raw_json=str(day),
        )
        db.add(record)
        records_saved += 1

    await db.commit()

    return {"status": "ok", "records_saved": records_saved, "days_synced": len(sleep_data.get("data", []))}


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
