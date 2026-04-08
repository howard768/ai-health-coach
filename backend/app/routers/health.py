from datetime import datetime
from fastapi import APIRouter

from app.schemas.health import DashboardResponse, MetricResponse, RecoveryResponse, CoachInsightResponse

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard():
    """Pre-computed dashboard data for the iOS client.

    In production, this pulls from the database (pre-computed by background sync).
    The iOS client just renders — no heavy computation on the client.
    """
    # Determine greeting
    hour = datetime.now().hour
    if 5 <= hour < 12:
        time_of_day = "morning"
    elif 12 <= hour < 17:
        time_of_day = "afternoon"
    elif 17 <= hour < 22:
        time_of_day = "evening"
    else:
        time_of_day = "night"

    return DashboardResponse(
        greeting=f"Good {time_of_day}, Brock",
        date=datetime.now().strftime("%A, %B %-d"),
        metrics=[
            MetricResponse(
                category="sleepEfficiency",
                label="Sleep Efficiency",
                value="91",
                unit="%",
                subtitle="7h 12m total",
                trend="positive",
            ),
            MetricResponse(
                category="hrv",
                label="HRV Status",
                value="68",
                unit="ms",
                subtitle="↑ 14% vs baseline",
                trend="positive",
            ),
            MetricResponse(
                category="restingHR",
                label="Resting HR",
                value="58",
                unit="bpm",
                subtitle="Stable this week",
                trend="neutral",
            ),
            MetricResponse(
                category="consistency",
                label="Consistency",
                value="5/7",
                unit="days",
                subtitle="On track this week",
                trend="positive",
            ),
        ],
        recovery=RecoveryResponse(level="High", description="Good for intensity today"),
        coach_insight=CoachInsightResponse(
            message="Your HRV is 14% above your 7-day baseline and sleep efficiency hit 91%. Great recovery night. Today is ideal for progressive overload on your leg day. Prioritize compound lifts.",
            timestamp=datetime.now().isoformat(),
        ),
        last_synced=datetime.now().isoformat(),
    )
