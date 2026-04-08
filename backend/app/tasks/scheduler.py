"""Background task scheduler for push notifications.

Uses APScheduler's AsyncIOScheduler to run periodic jobs.
All jobs check anti-fatigue gates before sending.
"""

import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select, desc

from app.database import async_session
from app.models.health import SleepRecord
from app.models.notification import DeviceToken, NotificationRecord
from app.services.apns import apns_client
from app.services.notification_engine import notification_engine
from app.services.notification_content import content_generator
from app.services.anti_fatigue import can_send
from app.services.notification_templates import seed_templates, pick_template
from app.services.coach_engine import SafetyCheck

logger = logging.getLogger("meld.scheduler")

USER_ID = "default"  # TODO: replace with real auth

scheduler = AsyncIOScheduler()


# ── Shared Helpers ──────────────────────────────────────────

async def _get_active_tokens(db) -> list:
    """Get all active device tokens (excluding test tokens)."""
    result = await db.execute(
        select(DeviceToken).where(
            DeviceToken.user_id == USER_ID,
            DeviceToken.is_active == True,
            DeviceToken.token != "test_token_abc123",
        )
    )
    return result.scalars().all()


async def _get_latest_health_data(db) -> dict:
    """Get latest health data from SleepRecord."""
    result = await db.execute(
        select(SleepRecord)
        .where(SleepRecord.user_id == USER_ID)
        .order_by(desc(SleepRecord.date))
        .limit(1)
    )
    sr = result.scalar_one_or_none()
    if not sr:
        return {}
    return {
        "sleep_efficiency": sr.efficiency,
        "hrv_average": sr.hrv_average,
        "resting_hr": sr.resting_hr,
        "readiness_score": sr.readiness_score,
        "total_sleep_hours": (sr.total_sleep_seconds or 0) / 3600,
    }


async def _send_notification(db, tokens: list, content: dict):
    """Send a notification to all active device tokens and log it."""
    for token_row in tokens:
        apns_result = await apns_client.send_push(
            device_token=token_row.token,
            title=content["title"],
            body=content["body"],
            category=content["apns"]["category"],
            thread_id=content["apns"]["thread_id"],
            interruption_level=content["apns"]["interruption_level"],
            relevance_score=content["apns"]["relevance_score"],
            collapse_id=content["apns"].get("collapse_id"),
            data=content["data"],
        )

        record = NotificationRecord(
            user_id=USER_ID,
            device_token_id=token_row.id,
            category=content["category"],
            title=content["title"],
            body=content["body"],
            payload_json=content,
        )
        db.add(record)

        if apns_result.get("success"):
            logger.info("%s sent to device %d", content["category"], token_row.id)
        else:
            logger.error("%s failed for device %d: %s", content["category"], token_row.id, apns_result.get("error"))
            if apns_result.get("status") == 410:
                token_row.is_active = False

    await db.commit()


# ── Jobs ────────────────────────────────────────────────────

async def morning_brief_job():
    """Daily morning brief with recovery score and coaching line.
    Uses templates first (DOVA: 40-60% cost savings), falls back to AI.
    """
    logger.info("Running morning_brief_job")
    async with async_session() as db:
        if not await can_send(db, USER_ID, "morning_brief"):
            return
        tokens = await _get_active_tokens(db)
        if not tokens:
            logger.info("No active tokens — skipping")
            return
        health_data = await _get_latest_health_data(db)

        # Determine context for template selection
        readiness = health_data.get("readiness_score", 0)
        context = "recovery_high" if readiness >= 67 else "recovery_moderate" if readiness >= 34 else "recovery_low"

        # Try template first (DOVA: no AI cost)
        template_content = await pick_template(db, "morning_brief", context, {"user_name": "Brock"})
        if template_content:
            content = {
                **template_content,
                "category": "morning_brief",
                "apns": {
                    "category": "MORNING_BRIEF",
                    "thread_id": "daily-coaching",
                    "interruption_level": "active",
                    "relevance_score": 0.8,
                },
                "data": {"deep_link": "meld://dashboard", "notification_type": "morning_brief"},
            }
            logger.info("Morning brief from template (context=%s)", context)
        else:
            # Fallback to AI generation
            content = notification_engine.generate_morning_brief(health_data, user_name="Brock")
            logger.info("Morning brief from AI (no template for context=%s)", context)

        await _send_notification(db, tokens, content)
    logger.info("morning_brief_job complete")


async def coaching_nudge_job():
    """Cross-domain insight notification. 2-3x per week."""
    logger.info("Running coaching_nudge_job")
    async with async_session() as db:
        if not await can_send(db, USER_ID, "coaching_nudge"):
            return
        tokens = await _get_active_tokens(db)
        if not tokens:
            logger.info("No active tokens — skipping")
            return
        health_data = await _get_latest_health_data(db)
        content = content_generator.generate_coaching_nudge(health_data, user_name="Brock")
        await _send_notification(db, tokens, content)
    logger.info("coaching_nudge_job complete")


async def bedtime_coaching_job():
    """Wind-down reminder timed to sleep window."""
    logger.info("Running bedtime_coaching_job")
    async with async_session() as db:
        if not await can_send(db, USER_ID, "bedtime_coaching"):
            return
        tokens = await _get_active_tokens(db)
        if not tokens:
            logger.info("No active tokens — skipping")
            return
        health_data = await _get_latest_health_data(db)
        content = content_generator.generate_bedtime_coaching(health_data, user_name="Brock")
        await _send_notification(db, tokens, content)
    logger.info("bedtime_coaching_job complete")


async def streak_saver_job():
    """Evening check — only fires when user is about to miss their streak."""
    logger.info("Running streak_saver_job")
    async with async_session() as db:
        if not await can_send(db, USER_ID, "streak_alerts"):
            return
        tokens = await _get_active_tokens(db)
        if not tokens:
            return

        # Calculate workout days this week from SleepRecord (readiness as proxy)
        # TODO: replace with real workout tracking
        from sqlalchemy import func as sqlfunc
        week_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = week_start.replace(day=week_start.day - week_start.weekday())
        result = await db.execute(
            select(sqlfunc.count(SleepRecord.id)).where(
                SleepRecord.user_id == USER_ID,
                SleepRecord.date >= week_start.strftime("%Y-%m-%d"),
                SleepRecord.readiness_score >= 50,
            )
        )
        active_days = result.scalar() or 0
        streak_goal = 5  # Default weekly goal

        content = content_generator.generate_streak_saver(active_days, streak_goal, user_name="Brock")
        if not content:
            logger.info("Streak on track (%d/%d) — no alert needed", active_days, streak_goal)
            return

        # Try template
        template = await pick_template(db, "streak_saver", "streak_at_risk", {
            "streak_count": str(active_days), "streak_goal": str(streak_goal),
        })
        if template:
            content["title"] = template["title"]
            content["body"] = template["body"]
            logger.info("Streak saver from template")

        await _send_notification(db, tokens, content)
    logger.info("streak_saver_job complete")


async def weekly_review_job():
    """Sunday evening weekly summary."""
    logger.info("Running weekly_review_job")
    async with async_session() as db:
        if not await can_send(db, USER_ID, "weekly_review"):
            return
        tokens = await _get_active_tokens(db)
        if not tokens:
            return

        # Get 7-day health data summary
        result = await db.execute(
            select(SleepRecord)
            .where(SleepRecord.user_id == USER_ID)
            .order_by(desc(SleepRecord.date))
            .limit(7)
        )
        records = result.scalars().all()

        workout_days = sum(1 for r in records if r.readiness_score and r.readiness_score >= 50)
        avg_sleep = sum(r.efficiency or 0 for r in records) / max(len(records), 1)
        sleep_trend = "improving" if avg_sleep > 75 else "stable" if avg_sleep > 60 else "declining"

        week_context = "positive_week" if sleep_trend == "improving" and workout_days >= 4 else \
                       "tough_week" if workout_days < 3 else "neutral_week"

        # Try template first
        template = await pick_template(db, "weekly_review", week_context, {
            "week_workout_days": str(workout_days),
        })

        content = content_generator.generate_weekly_review(
            {"workout_days": workout_days, "sleep_trend": sleep_trend},
            user_name="Brock",
        )
        if template:
            content["title"] = template["title"]
            content["body"] = template["body"]
            logger.info("Weekly review from template (context=%s)", week_context)

        await _send_notification(db, tokens, content)
    logger.info("weekly_review_job complete")


async def health_alert_job():
    """Check health data for concerning deviations after sync."""
    logger.info("Running health_alert_job")
    async with async_session() as db:
        if not await can_send(db, USER_ID, "health_alerts"):
            return
        tokens = await _get_active_tokens(db)
        if not tokens:
            return

        health_data = await _get_latest_health_data(db)
        if not health_data:
            return

        # Use the CoachEngine's SafetyCheck for deterministic detection
        safety = SafetyCheck.check_health_data(health_data)
        if not safety.is_concerning:
            logger.info("Health data normal — no alert")
            return

        content = content_generator.generate_health_alert(health_data, safety.reasons)
        if not content:
            return

        # Try template
        context = "concerning" if safety.requires_opus else "metric_deviation"
        template = await pick_template(db, "health_alert", context)
        if template:
            content["title"] = template["title"]
            content["body"] = template["body"]

        await _send_notification(db, tokens, content)
        logger.info("Health alert sent: %s", safety.reasons)
    logger.info("health_alert_job complete")


# ── Scheduler Setup ─────────────────────────────────────────

async def _seed_on_start():
    """Seed notification templates on scheduler start."""
    async with async_session() as db:
        await seed_templates(db)


def start_scheduler():
    """Initialize and start the scheduler with all jobs."""
    # Seed templates
    import asyncio
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_seed_on_start())
    except RuntimeError:
        asyncio.run(_seed_on_start())

    # Morning brief: 08:00 UTC daily
    scheduler.add_job(
        morning_brief_job,
        trigger=CronTrigger(hour=8, minute=0),
        id="morning_brief",
        name="Morning Brief",
        replace_existing=True,
    )

    # Coaching nudge: Mon/Wed/Fri at 12:00 UTC
    scheduler.add_job(
        coaching_nudge_job,
        trigger=CronTrigger(day_of_week="mon,wed,fri", hour=12, minute=0),
        id="coaching_nudge",
        name="Coaching Nudge",
        replace_existing=True,
    )

    # Bedtime coaching: daily at 22:00 UTC
    scheduler.add_job(
        bedtime_coaching_job,
        trigger=CronTrigger(hour=22, minute=0),
        id="bedtime_coaching",
        name="Bedtime Coaching",
        replace_existing=True,
    )

    # Streak saver: daily at 18:00 UTC (evening check)
    scheduler.add_job(
        streak_saver_job,
        trigger=CronTrigger(hour=18, minute=0),
        id="streak_saver",
        name="Streak Saver",
        replace_existing=True,
    )

    # Weekly review: Sundays at 18:00 UTC
    scheduler.add_job(
        weekly_review_job,
        trigger=CronTrigger(day_of_week="sun", hour=18, minute=0),
        id="weekly_review",
        name="Weekly Review",
        replace_existing=True,
    )

    # Health alert: every 6 hours (checks for deviations)
    scheduler.add_job(
        health_alert_job,
        trigger=CronTrigger(hour="*/6"),
        id="health_alert",
        name="Health Alert Check",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Notification scheduler started with %d jobs", len(scheduler.get_jobs()))


def stop_scheduler():
    """Gracefully shut down the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Notification scheduler stopped")
