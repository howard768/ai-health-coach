"""Notification management endpoints.

Handles device token registration, notification preferences,
test notifications, and open tracking.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.notification import DeviceToken, NotificationRecord, NotificationPreference
from app.services.apns import apns_client
from app.services.notification_engine import notification_engine
from app.services.notification_content import content_generator

logger = logging.getLogger("meld.notifications")

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

USER_ID = "default"  # TODO: replace with real auth


# ── Request/Response Models ─────────────────────────────────

class RegisterTokenRequest(BaseModel):
    device_token: str
    platform: str = "ios"


class RegisterTokenResponse(BaseModel):
    status: str
    message: str


class NotificationPreferencesResponse(BaseModel):
    morning_brief: bool = True
    coaching_nudge: bool = True
    bedtime_coaching: bool = True
    streak_alerts: bool = True
    weekly_review: bool = True
    workout_reminders: bool = False
    health_alerts: bool = True
    quiet_hours_start: str = "22:00"
    quiet_hours_end: str = "07:00"


class TestNotificationResponse(BaseModel):
    status: str
    notification_id: int | None = None
    apns_result: dict | None = None
    content: dict | None = None


# ── Endpoints ───────────────────────────────────────────────

@router.post("/register", response_model=RegisterTokenResponse)
async def register_device_token(
    request: RegisterTokenRequest, db: AsyncSession = Depends(get_db)
):
    """Register or update an APNs device token."""
    # Check if token already exists
    result = await db.execute(
        select(DeviceToken).where(DeviceToken.token == request.device_token)
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.user_id = USER_ID
        existing.is_active = True
        existing.updated_at = datetime.utcnow()
        logger.info("Updated device token %s...%s", request.device_token[:8], request.device_token[-4:])
    else:
        token = DeviceToken(
            user_id=USER_ID,
            token=request.device_token,
            platform=request.platform,
        )
        db.add(token)
        logger.info("Registered new device token %s...%s", request.device_token[:8], request.device_token[-4:])

    await db.commit()
    return RegisterTokenResponse(status="ok", message="Token registered")


@router.post("/test", response_model=TestNotificationResponse)
async def send_test_notification(db: AsyncSession = Depends(get_db)):
    """Send a test morning brief notification (dev endpoint)."""
    # Get active device token (skip test tokens)
    result = await db.execute(
        select(DeviceToken).where(
            DeviceToken.user_id == USER_ID,
            DeviceToken.is_active == True,
            DeviceToken.token != "test_token_abc123",
        )
    )
    token_row = result.scalar_one_or_none()
    if not token_row:
        return TestNotificationResponse(
            status="error",
            content={"message": "No registered device token found"},
        )

    # Get latest health data for content generation
    from app.models.health import SleepRecord
    from sqlalchemy import desc

    sleep_result = await db.execute(
        select(SleepRecord)
        .where(SleepRecord.user_id == USER_ID)
        .order_by(desc(SleepRecord.date))
        .limit(1)
    )
    sleep_record = sleep_result.scalar_one_or_none()

    health_data = {}
    if sleep_record:
        health_data = {
            "sleep_efficiency": sleep_record.efficiency,
            "hrv_average": sleep_record.hrv_average,
            "resting_hr": sleep_record.resting_hr,
            "readiness_score": sleep_record.readiness_score,
            "total_sleep_hours": (sleep_record.total_sleep_seconds or 0) / 3600,
        }

    # Generate content
    content = notification_engine.generate_morning_brief(health_data, user_name="Brock")

    # Send via APNs
    apns_result = await apns_client.send_push(
        device_token=token_row.token,
        title=content["title"],
        body=content["body"],
        category=content["apns"]["category"],
        thread_id=content["apns"]["thread_id"],
        interruption_level=content["apns"]["interruption_level"],
        relevance_score=content["apns"]["relevance_score"],
        collapse_id=content["apns"]["collapse_id"],
        data=content["data"],
    )

    # Log the notification
    record = NotificationRecord(
        user_id=USER_ID,
        device_token_id=token_row.id,
        category=content["category"],
        title=content["title"],
        body=content["body"],
        payload_json=content,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    return TestNotificationResponse(
        status="sent" if apns_result.get("success") else "failed",
        notification_id=record.id,
        apns_result=apns_result,
        content={"title": content["title"], "body": content["body"]},
    )


@router.post("/test/{category}")
async def send_test_by_category(category: str, db: AsyncSession = Depends(get_db)):
    """Send a test notification for any category (dev endpoint)."""
    from sqlalchemy import desc
    from app.models.health import SleepRecord

    result = await db.execute(
        select(DeviceToken).where(
            DeviceToken.user_id == USER_ID,
            DeviceToken.is_active == True,
            DeviceToken.token != "test_token_abc123",
        )
    )
    token_row = result.scalar_one_or_none()
    if not token_row:
        return {"status": "error", "message": "No device token"}

    sleep_result = await db.execute(
        select(SleepRecord).where(SleepRecord.user_id == USER_ID).order_by(desc(SleepRecord.date)).limit(1)
    )
    sr = sleep_result.scalar_one_or_none()
    health_data = {
        "sleep_efficiency": sr.efficiency if sr else 85,
        "hrv_average": sr.hrv_average if sr else 65,
        "resting_hr": sr.resting_hr if sr else 58,
        "readiness_score": sr.readiness_score if sr else 80,
    }

    if category == "coaching_nudge":
        content = content_generator.generate_coaching_nudge(health_data, user_name="Brock")
    elif category == "bedtime_coaching":
        content = content_generator.generate_bedtime_coaching(health_data, user_name="Brock")
    elif category == "morning_brief":
        content = notification_engine.generate_morning_brief(health_data, user_name="Brock")
    elif category == "streak_saver":
        content = content_generator.generate_streak_saver(3, 5, user_name="Brock")
        if not content:
            return {"status": "skipped", "message": "No streak at risk"}
    elif category == "weekly_review":
        content = content_generator.generate_weekly_review(
            {"workout_days": 4, "sleep_trend": "improving"}, user_name="Brock"
        )
    elif category == "health_alert":
        content = content_generator.generate_health_alert(
            health_data, ["HRV deviation detected"]
        )
        if not content:
            return {"status": "skipped", "message": "No concerning data"}
    else:
        return {"status": "error", "message": f"Unknown category: {category}"}

    apns_result = await apns_client.send_push(
        device_token=token_row.token,
        title=content["title"],
        body=content["body"],
        category=content["apns"]["category"],
        thread_id=content["apns"]["thread_id"],
        interruption_level=content["apns"]["interruption_level"],
        relevance_score=content["apns"]["relevance_score"],
        data=content["data"],
    )

    record = NotificationRecord(
        user_id=USER_ID, device_token_id=token_row.id,
        category=content["category"], title=content["title"],
        body=content["body"], payload_json=content,
    )
    db.add(record)
    await db.commit()

    return {
        "status": "sent" if apns_result.get("success") else "failed",
        "content": {"title": content["title"], "body": content["body"]},
        "apns_result": apns_result,
    }


@router.get("/preferences", response_model=NotificationPreferencesResponse)
async def get_notification_preferences(db: AsyncSession = Depends(get_db)):
    """Get notification preferences for the current user."""
    result = await db.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == USER_ID)
    )
    pref = result.scalar_one_or_none()

    if not pref:
        # Return defaults (no row yet — will be created on first PUT)
        return NotificationPreferencesResponse()

    return NotificationPreferencesResponse(
        morning_brief=pref.morning_brief,
        coaching_nudge=pref.coaching_nudge,
        bedtime_coaching=pref.bedtime_coaching,
        streak_alerts=pref.streak_alerts,
        weekly_review=pref.weekly_review,
        workout_reminders=pref.workout_reminders,
        health_alerts=pref.health_alerts,
        quiet_hours_start=pref.quiet_hours_start,
        quiet_hours_end=pref.quiet_hours_end,
    )


@router.put("/preferences", response_model=NotificationPreferencesResponse)
async def update_notification_preferences(
    prefs: NotificationPreferencesResponse, db: AsyncSession = Depends(get_db)
):
    """Update notification preferences. Creates row if it doesn't exist."""
    result = await db.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == USER_ID)
    )
    pref = result.scalar_one_or_none()

    if pref:
        pref.morning_brief = prefs.morning_brief
        pref.coaching_nudge = prefs.coaching_nudge
        pref.bedtime_coaching = prefs.bedtime_coaching
        pref.streak_alerts = prefs.streak_alerts
        pref.weekly_review = prefs.weekly_review
        pref.workout_reminders = prefs.workout_reminders
        pref.health_alerts = prefs.health_alerts
        pref.quiet_hours_start = prefs.quiet_hours_start
        pref.quiet_hours_end = prefs.quiet_hours_end
    else:
        pref = NotificationPreference(
            user_id=USER_ID,
            morning_brief=prefs.morning_brief,
            coaching_nudge=prefs.coaching_nudge,
            bedtime_coaching=prefs.bedtime_coaching,
            streak_alerts=prefs.streak_alerts,
            weekly_review=prefs.weekly_review,
            workout_reminders=prefs.workout_reminders,
            health_alerts=prefs.health_alerts,
            quiet_hours_start=prefs.quiet_hours_start,
            quiet_hours_end=prefs.quiet_hours_end,
        )
        db.add(pref)

    await db.commit()
    logger.info("Updated notification preferences for user %s", USER_ID)

    return prefs


@router.post("/opened")
async def report_notification_opened(
    notification_id: int, db: AsyncSession = Depends(get_db)
):
    """Track when a user opens a notification (for anti-fatigue metrics)."""
    result = await db.execute(
        select(NotificationRecord).where(NotificationRecord.id == notification_id)
    )
    record = result.scalar_one_or_none()
    if record:
        record.opened_at = datetime.utcnow()
        await db.commit()
        return {"status": "ok"}
    return {"status": "not_found"}
