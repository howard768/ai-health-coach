"""Background task scheduler for push notifications.

Uses APScheduler's AsyncIOScheduler to run periodic jobs.
All jobs check anti-fatigue gates before sending.
"""

import logging
from datetime import datetime

import httpx
from apscheduler.jobstores.base import JobLookupError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select, desc
from sqlalchemy.exc import SQLAlchemyError

from app.database import async_session
from app.models.health import SleepRecord
from app.models.notification import DeviceToken, NotificationRecord
from app.services.apns import apns_client
from app.services.notification_engine import notification_engine
from app.services.notification_content import content_generator
from app.services.anti_fatigue import can_send
from app.services.notification_templates import seed_templates, pick_template
from app.services.coach_engine import SafetyCheck
from app.services.health_data import get_latest_health_data
from app.services.oura_sync import sync_user_data as oura_sync
from app.services.peloton_sync import sync_user_data as peloton_sync
from app.services.garmin_sync import sync_user_data as garmin_sync
from app.services.data_reconciliation import reconcile_day
from app.services.correlation_engine import compute_correlations
from app.services.literature import literature_service
from app.services.oura_webhooks import list_subscriptions, renew_subscription
from app.services.offline_eval import run_offline_eval
from app.core.constants import ReadinessThreshold, TEST_DEVICE_TOKEN
from app.core.time import utcnow_naive

logger = logging.getLogger("meld.scheduler")

scheduler = AsyncIOScheduler()


# ── User discovery ──────────────────────────────────────────
#
# Scheduler jobs run outside request context — they can't use Depends(current_user).
# For the current single-user model, we look up the first active non-placeholder
# user and use its apple_user_id. After migration, we'd iterate all active users.

async def _get_primary_user_id(db) -> str | None:
    """Return the apple_user_id of the primary active user.

    Skips the 'default' placeholder created by the auth migration. Returns
    None if no real user exists yet (e.g. fresh deploy before first sign-in).
    """
    from app.models.user import User
    result = await db.execute(
        select(User)
        .where(User.is_active == True, User.apple_user_id != "default")
        .order_by(User.created_at)
        .limit(1)
    )
    user = result.scalar_one_or_none()
    if user is None:
        # Fall back to the 'default' row if it still exists — lets local dev
        # work before any real user has signed in.
        result = await db.execute(
            select(User).where(User.apple_user_id == "default").limit(1)
        )
        user = result.scalar_one_or_none()
    return user.apple_user_id if user else None


async def _get_primary_user(db):
    """Return the primary User object (or None if no real user exists)."""
    user_id = await _get_primary_user_id(db)
    if user_id is None:
        return None
    from app.models.user import User
    result = await db.execute(select(User).where(User.apple_user_id == user_id))
    return result.scalar_one_or_none()


def _first_name_of(user) -> str:
    """Get first name for notification templates, or 'there' as fallback."""
    if user and user.name:
        return user.name.split()[0]
    return "there"


# ── Shared Helpers ──────────────────────────────────────────

async def _get_active_tokens(db, user_id: str) -> list:
    """Get all active device tokens for a user (excluding test tokens)."""
    result = await db.execute(
        select(DeviceToken).where(
            DeviceToken.user_id == user_id,
            DeviceToken.is_active == True,
            DeviceToken.token != TEST_DEVICE_TOKEN,
        )
    )
    return result.scalars().all()


async def _get_latest_health_data(db, user_id: str) -> dict:
    """Get latest reconciled health data for scheduler jobs.

    Delegates to the canonical health_data.get_latest_health_data() so that
    scheduler notifications use the same multi-source reconciled data as the
    coach and dashboard — not stale SleepRecord-only data.
    """
    return await get_latest_health_data(db, user_id)


async def _send_notification(db, user_id: str, tokens: list, content: dict):
    """Send a notification to all active device tokens for a user and log it."""
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
            media_url=content.get("media_url"),
        )

        record = NotificationRecord(
            user_id=user_id,
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

# P2-2: Shared shell for all notification jobs.
#
# The 6 notification jobs (morning_brief, coaching_nudge, bedtime_coaching,
# streak_saver, weekly_review, health_alert) all share the same boilerplate:
#   1. Open a DB session
#   2. Load the primary user (skip if none)
#   3. Gate on can_send(category)
#   4. Load active device tokens (skip if none)
#   5. Build notification content (job-specific — provided via callback)
#   6. Send notification if content is non-None
#
# The old code duplicated steps 1-4 and 6 across all six jobs. Extracting
# the shell leaves each job as just the content-building callback.
async def _run_notification_job(
    job_name: str,
    category: str,
    content_fn,
) -> None:
    """Shared shell for scheduler notification jobs.

    Args:
        job_name: Human-readable name for logging (e.g. "morning_brief_job").
        category: Anti-fatigue category key — passed to `can_send()`.
        content_fn: async callable(db, user_id, user_name) -> dict | None.
            Return None to skip the notification (e.g. streak on track,
            no concerning health data, frequency preference says skip).
    """
    logger.info("Running %s", job_name)
    async with async_session() as db:
        user = await _get_primary_user(db)
        if user is None:
            logger.info("No active user — skipping %s", job_name)
            return
        user_id = user.apple_user_id
        user_name = _first_name_of(user)

        if not await can_send(db, user_id, category):
            return

        tokens = await _get_active_tokens(db, user_id)
        if not tokens:
            logger.info("No active tokens — skipping %s", job_name)
            return

        content = await content_fn(db, user_id, user_name)
        if not content:
            return

        await _send_notification(db, user_id, tokens, content)
    logger.info("%s complete", job_name)


async def morning_brief_job():
    """Daily morning brief with recovery score and coaching line.
    Uses templates first (DOVA: 40-60% cost savings), falls back to AI.
    """
    async def build(db, user_id, user_name):
        health_data = await _get_latest_health_data(db, user_id)

        # Determine context for template selection
        readiness = health_data.get("readiness_score", 0)
        context = (
            "recovery_high" if readiness >= ReadinessThreshold.HIGH
            else "recovery_moderate" if readiness >= ReadinessThreshold.MODERATE
            else "recovery_low"
        )

        # Try template first (DOVA: no AI cost)
        template_content = await pick_template(
            db, "morning_brief", context, {"user_name": user_name}
        )
        if template_content:
            logger.info("Morning brief from template (context=%s)", context)
            return {
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
        # Fallback to AI generation
        logger.info("Morning brief from AI (no template for context=%s)", context)
        return notification_engine.generate_morning_brief(health_data, user_name=user_name)

    await _run_notification_job("morning_brief_job", "morning_brief", build)


async def coaching_nudge_job():
    """Cross-domain insight notification. Frequency set by user preference."""
    async def build(db, user_id, user_name):
        # Check frequency preference
        from app.models.notification import NotificationPreference
        pref_result = await db.execute(
            select(NotificationPreference).where(NotificationPreference.user_id == user_id)
        )
        pref = pref_result.scalar_one_or_none()
        frequency = pref.nudge_frequency if pref else "2x_week"

        today = utcnow_naive().weekday()  # 0=Mon, 6=Sun
        if frequency == "weekly" and today != 0:
            logger.info("Nudge frequency is weekly, today is not Monday — skipping")
            return None
        if frequency == "2x_week" and today not in (0, 3):  # Mon, Thu
            logger.info("Nudge frequency is 2x/week, today is not Mon/Thu — skipping")
            return None
        # "daily" sends every day — no skip

        health_data = await _get_latest_health_data(db, user_id)
        return content_generator.generate_coaching_nudge(health_data, user_name=user_name)

    await _run_notification_job("coaching_nudge_job", "coaching_nudge", build)


async def bedtime_coaching_job():
    """Wind-down reminder timed to sleep window."""
    async def build(db, user_id, user_name):
        health_data = await _get_latest_health_data(db, user_id)
        return content_generator.generate_bedtime_coaching(health_data, user_name=user_name)

    await _run_notification_job("bedtime_coaching_job", "bedtime_coaching", build)


async def streak_saver_job():
    """Evening check — only fires when user is about to miss their streak."""
    async def build(db, user_id, user_name):
        # Calculate active days this week using readiness as proxy for workout days.
        from sqlalchemy import func as sqlfunc
        from datetime import timedelta
        today = utcnow_naive().replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today - timedelta(days=today.weekday())
        result = await db.execute(
            select(sqlfunc.count(SleepRecord.id)).where(
                SleepRecord.user_id == user_id,
                SleepRecord.date >= week_start.strftime("%Y-%m-%d"),
                SleepRecord.readiness_score >= 50,
            )
        )
        active_days = result.scalar() or 0
        streak_goal = 5

        content = content_generator.generate_streak_saver(
            active_days, streak_goal, user_name=user_name
        )
        if not content:
            logger.info("Streak on track (%d/%d) — no alert needed", active_days, streak_goal)
            return None

        template = await pick_template(db, "streak_saver", "streak_at_risk", {
            "streak_count": str(active_days), "streak_goal": str(streak_goal),
        })
        if template:
            content["title"] = template["title"]
            content["body"] = template["body"]
        return content

    await _run_notification_job("streak_saver_job", "streak_alerts", build)


async def weekly_review_job():
    """Sunday evening weekly summary."""
    async def build(db, user_id, user_name):
        result = await db.execute(
            select(SleepRecord)
            .where(SleepRecord.user_id == user_id)
            .order_by(desc(SleepRecord.date))
            .limit(7)
        )
        records = result.scalars().all()

        workout_days = sum(1 for r in records if r.readiness_score and r.readiness_score >= 50)
        avg_sleep = sum(r.efficiency or 0 for r in records) / max(len(records), 1)
        sleep_trend = "improving" if avg_sleep > 75 else "stable" if avg_sleep > 60 else "declining"

        week_context = "positive_week" if sleep_trend == "improving" and workout_days >= 4 else \
                       "tough_week" if workout_days < 3 else "neutral_week"

        template = await pick_template(db, "weekly_review", week_context, {
            "week_workout_days": str(workout_days),
        })

        content = content_generator.generate_weekly_review(
            {"workout_days": workout_days, "sleep_trend": sleep_trend},
            user_name=user_name,
        )
        if template:
            content["title"] = template["title"]
            content["body"] = template["body"]
        return content

    await _run_notification_job("weekly_review_job", "weekly_review", build)


async def health_alert_job():
    """Check health data for concerning deviations after sync."""
    async def build(db, user_id, user_name):
        health_data = await _get_latest_health_data(db, user_id)
        if not health_data:
            return None

        safety = SafetyCheck.check_health_data(health_data)
        if not safety.is_concerning:
            return None

        content = content_generator.generate_health_alert(health_data, safety.reasons)
        if not content:
            return None

        context = "concerning" if safety.requires_opus else "metric_deviation"
        template = await pick_template(db, "health_alert", context)
        if template:
            content["title"] = template["title"]
            content["body"] = template["body"]

        logger.info("Health alert sent: %s", safety.reasons)
        return content

    await _run_notification_job("health_alert_job", "health_alerts", build)


async def oura_sync_job():
    """Automatically sync latest Oura data every 6 hours."""
    logger.info("Running oura_sync_job")
    async with async_session() as db:
        user_id = await _get_primary_user_id(db)
        if user_id is None:
            return
        result = await oura_sync(db, user_id)
        logger.info("Oura sync result: %s", result)
        today = utcnow_naive().strftime("%Y-%m-%d")
        await reconcile_day(db, user_id, today)


async def peloton_sync_job():
    """Sync Peloton workout data every 6 hours."""
    logger.info("Running peloton_sync_job")
    async with async_session() as db:
        user_id = await _get_primary_user_id(db)
        if user_id is None:
            return
        result = await peloton_sync(db, user_id)
        logger.info("Peloton sync result: %s", result)
        if result.get("status") == "ok":
            today = utcnow_naive().strftime("%Y-%m-%d")
            await reconcile_day(db, user_id, today)


async def garmin_sync_job():
    """Sync Garmin health data every 6 hours."""
    logger.info("Running garmin_sync_job")
    async with async_session() as db:
        user_id = await _get_primary_user_id(db)
        if user_id is None:
            return
        result = await garmin_sync(db, user_id)
        logger.info("Garmin sync result: %s", result)
        if result.get("status") == "ok":
            today = utcnow_naive().strftime("%Y-%m-%d")
            await reconcile_day(db, user_id, today)


async def webhook_renewal_job():
    """Monthly: renew Oura webhook subscriptions before they expire (90-day TTL)."""
    logger.info("Running webhook_renewal_job")
    try:
        subs = await list_subscriptions()
        renewed = 0
        for sub in subs:
            try:
                await renew_subscription(sub["id"])
                renewed += 1
            except (httpx.HTTPError, KeyError, ValueError) as e:
                logger.error("Failed to renew webhook %s: %s", sub["id"], e)
        logger.info("Renewed %d/%d webhook subscriptions", renewed, len(subs))
    except (httpx.HTTPError, ValueError) as e:
        logger.error("Webhook renewal failed: %s", e)


async def feature_refresh_job():
    """Nightly: materialize the Signal Engine feature store for the primary user.

    Rebuilds the trailing 30 days of derived features so downstream ML jobs
    (correlation engine, forecasting, ranker) always read a fresh, consistent
    frame. Idempotent — rerunning the same day is a no-op against the data
    (values may change as new Oura webhook rows land, which is the point).

    Kept under the 60-second budget per the Phase 1 acceptance criteria in
    ``~/.claude/plans/golden-floating-creek.md``. Scheduled at 03:30 UTC so
    it completes before the correlation engine runs at 04:00 UTC on Sundays
    and before morning brief in any user timezone.
    """
    from datetime import date

    # Lazy import per boundary rules — the rest of app/ only reaches into
    # ``ml.api`` (see tests/ml/test_boundary.py).
    from ml import api as ml_api

    logger.info("Running feature_refresh_job")
    async with async_session() as db:
        user_id = await _get_primary_user_id(db)
        if user_id is None:
            logger.info("feature_refresh_job: no primary user yet, skipping")
            return
        try:
            rows = await ml_api.refresh_features_for_user(
                db, user_id, through_date=date.today(), lookback_days=30
            )
            await db.commit()
            logger.info(
                "feature_refresh_job: wrote %d rows for user %s",
                rows,
                user_id,
            )
        except SQLAlchemyError as e:
            await db.rollback()
            logger.exception("feature_refresh_job DB error: %s", e)


async def insight_candidate_job():
    """Daily: generate candidates, rank them, persist the top-N slate.

    Shadow mode: writes to ``ml_rankings`` with ``was_shown=False``. The
    ``/api/insights/daily`` endpoint flips ``was_shown=True`` on read when
    ``ml_shadow_insight_card`` is off. Until then the slate is a shadow
    log for A/B comparison and for future ranker training.

    Caps (1/day, 3/week) are enforced at read time via
    ``ml.ranking.heuristic.can_surface_today``. The job itself writes
    rankings regardless, so the shadow log captures full exposure history.
    """
    from ml import api as ml_api

    logger.info("Running insight_candidate_job")
    async with async_session() as db:
        user_id = await _get_primary_user_id(db)
        if user_id is None:
            logger.info("insight_candidate_job: no primary user yet, skipping")
            return
        try:
            report = await ml_api.run_daily_insights(db, user_id)
            await db.commit()
            logger.info(
                "insight_candidate_job done (shadow=%s): %d candidates, %d rankings, top=%s",
                report.shadow_mode,
                report.candidates_generated,
                report.rankings_written,
                report.top_candidate_id,
            )
        except SQLAlchemyError as e:
            await db.rollback()
            logger.exception("insight_candidate_job DB error: %s", e)


async def baselines_job():
    """Nightly: run L1 baselines, forecasts, and residual anomaly detection.

    Shadow mode: populates ``ml_baselines``, ``ml_change_points``,
    ``ml_forecasts``, ``ml_anomalies`` but nothing user-facing reads them
    yet. Phase 3 wires L2 associations to use baselines; Phase 4 wires
    insight candidates to use anomalies.
    """
    from datetime import date as _date

    from ml import api as ml_api

    logger.info("Running baselines_job")
    async with async_session() as db:
        user_id = await _get_primary_user_id(db)
        if user_id is None:
            logger.info("baselines_job: no primary user yet, skipping")
            return
        try:
            report = await ml_api.run_discovery_pipeline(db, user_id)
            await db.commit()
            logger.info(
                "baselines_job done (shadow=%s): layers=%s counts=%s",
                report.shadow_mode,
                report.layers_run,
                report.tier_counts,
            )
        except SQLAlchemyError as e:
            await db.rollback()
            logger.exception("baselines_job DB error: %s", e)


async def correlation_engine_job():
    """Weekly: discover cross-domain health correlations from user data.

    Routes through ``ml.api.run_associations`` (Phase 3). The legacy
    ``compute_correlations`` in ``app/services/correlation_engine.py`` is
    preserved for the parity test but no longer exercised in production.
    """
    from ml import api as ml_api

    logger.info("Running correlation_engine_job (via ml.api.run_associations)")
    async with async_session() as db:
        user_id = await _get_primary_user_id(db)
        if user_id is None:
            logger.info("correlation_engine_job: no primary user yet, skipping")
            return
        try:
            report = await ml_api.run_associations(db, user_id, window_days=30)
            await db.commit()
            logger.info(
                "correlation_engine_job done: tested=%d sig=%d dynamic=%d rows=%d",
                report.pairs_tested,
                report.significant_results,
                report.dynamic_pairs_generated,
                report.rows_written,
            )
        except SQLAlchemyError as e:
            await db.rollback()
            logger.exception("correlation_engine_job DB error: %s", e)


async def granger_causal_job():
    """Weekly: L3 Granger causality + L4 DoWhy quasi-causal on developing+ pairs.

    Runs after ``correlation_engine_job`` (04:00) so fresh L2 associations
    are available. Shadow-gated behind ``ml_shadow_granger_causal``.
    Phase 6 of the Signal Engine.
    """
    from ml import api as ml_api

    if not ml_api.is_shadow_enabled("granger_causal"):
        logger.info("granger_causal_job: shadow flag off, skipping")
        return

    logger.info("Running granger_causal_job (L3 + L4)")
    async with async_session() as db:
        user_id = await _get_primary_user_id(db)
        if user_id is None:
            logger.info("granger_causal_job: no primary user yet, skipping")
            return
        try:
            granger_report = await ml_api.run_granger(db, user_id, window_days=90)
            logger.info(
                "granger_causal_job L3: tested=%d significant=%d updated=%d",
                granger_report.pairs_tested,
                granger_report.pairs_significant,
                granger_report.correlations_updated,
            )

            causal_report = await ml_api.run_causal(
                db, user_id, window_days=90, max_pairs=10
            )
            logger.info(
                "granger_causal_job L4: tested=%d passed=%d updated=%d",
                causal_report.pairs_tested,
                causal_report.pairs_passed,
                causal_report.correlations_updated,
            )

            await db.commit()
        except SQLAlchemyError as e:
            await db.rollback()
            logger.exception("granger_causal_job DB error: %s", e)
        except Exception as e:
            await db.rollback()
            logger.exception("granger_causal_job error: %s", e)


async def offline_eval_job():
    """Weekly: evaluate recent coach responses for quality regressions."""
    logger.info("Running offline_eval_job")
    async with async_session() as db:
        report = await run_offline_eval(db, days=7)
        logger.info(
            "Offline eval complete: %d evaluated, reading %.0f%%, grounding %.0f%%, %d flagged",
            report.get("total_evaluated", 0),
            report.get("reading_level", {}).get("pass_rate", 0),
            report.get("data_grounding", {}).get("pass_rate", 0),
            len(report.get("flagged_for_review", [])),
        )


async def synth_drift_job():
    """Daily: compare synth vs real biometrics, log drift, write HTML.

    Phase 4.5 Commit 5 wiring. The report reads from HealthMetricRecord
    partitioned on ``is_synthetic`` (Commit 3 column). When either
    partition is below the min-samples floor (e.g., synth hasn't been
    generated in this environment yet) the job short-circuits with
    ``dataset_too_small=True`` and logs. Cheap noise, no drama.

    The HTML path is best-effort: Evidently 0.7.21 fails to import on
    Python 3.14 (pydantic v1 incompat); Railway runs 3.12 so it works
    there. On failure ``html_path`` is None and only the KS summary
    is logged. No DB writes here; no commit needed.
    """
    from ml import api as ml_api

    logger.info("Running synth_drift_job")
    async with async_session() as db:
        try:
            report = await ml_api.build_synth_drift_report(db)
        except SQLAlchemyError as e:
            logger.exception("synth_drift_job DB error: %s", e)
            return
        except Exception as e:  # noqa: BLE001 -- scheduler must not crash on job errors
            logger.exception("synth_drift_job unexpected error: %s", e)
            return

    if report.dataset_too_small:
        logger.info(
            "synth_drift_job: dataset too small (ref=%d, cur=%d); nothing to compare yet",
            report.n_reference_rows,
            report.n_current_rows,
        )
        return

    logger.info(
        "synth_drift_job done: ref=%d cur=%d tested=%s drifted=%s html=%s backend=%s",
        report.n_reference_rows,
        report.n_current_rows,
        report.metrics_tested,
        report.drifted_metrics,
        report.html_path or "<none>",
        report.html_backend,
    )


async def get_personalized_timing(db, user_id: str) -> dict:
    """Calculate rolling 7-day average wake/sleep times from Oura data.

    Returns dict with wake_hour, wake_minute, bedtime_hour, bedtime_minute.
    Falls back to defaults if insufficient data.
    """
    result = await db.execute(
        select(SleepRecord)
        .where(
            SleepRecord.user_id == user_id,
            SleepRecord.bedtime_start.isnot(None),
            SleepRecord.bedtime_end.isnot(None),
        )
        .order_by(desc(SleepRecord.date))
        .limit(7)
    )
    records = result.scalars().all()

    if len(records) < 3:
        return {"wake_hour": 8, "wake_minute": 0, "bedtime_hour": 22, "bedtime_minute": 0}

    # Average bedtime_start (sleep time) and bedtime_end (wake time)
    sleep_minutes = []
    wake_minutes = []
    for r in records:
        if r.bedtime_start:
            h, m = map(int, r.bedtime_start.split(":"))
            # Handle after-midnight bedtimes (e.g., 01:30 = 25*60+30 for averaging)
            total = h * 60 + m
            if total < 12 * 60:  # Before noon = after midnight
                total += 24 * 60
            sleep_minutes.append(total)
        if r.bedtime_end:
            h, m = map(int, r.bedtime_end.split(":"))
            wake_minutes.append(h * 60 + m)

    if not sleep_minutes or not wake_minutes:
        return {"wake_hour": 8, "wake_minute": 0, "bedtime_hour": 22, "bedtime_minute": 0}

    avg_sleep = sum(sleep_minutes) / len(sleep_minutes)
    avg_wake = sum(wake_minutes) // len(wake_minutes)

    # Normalize back from 24+ hour range
    avg_sleep = avg_sleep % (24 * 60)

    return {
        "wake_hour": avg_wake // 60,
        "wake_minute": avg_wake % 60,
        "bedtime_hour": avg_sleep // 60,
        "bedtime_minute": avg_sleep % 60,
    }


async def timing_refresh_job():
    """Recalculate personalized notification timing from Oura sleep data.

    Runs daily at 03:00 UTC. Reschedules morning brief and bedtime coaching
    with updated times based on rolling 7-day sleep patterns.
    """
    logger.info("Running timing_refresh_job")
    async with async_session() as db:
        user_id = await _get_primary_user_id(db)
        if user_id is None:
            logger.info("No active user — skipping timing refresh")
            return
        timing = await get_personalized_timing(db, user_id)

    # Reschedule in the user's local timezone (P1-18 fix). Without this,
    # personalized timing fired in UTC — defeating the point of personalization.
    from app.config import settings as _settings
    user_tz = _settings.user_timezone

    # Reschedule morning brief: 30 min after average wake time
    wake_hour = timing["wake_hour"]
    wake_minute = timing["wake_minute"] + 30
    if wake_minute >= 60:
        wake_hour = (wake_hour + 1) % 24  # Modulo 24 to avoid hour=24 crash
        wake_minute -= 60

    try:
        scheduler.reschedule_job(
            "morning_brief",
            trigger=CronTrigger(hour=wake_hour, minute=wake_minute, timezone=user_tz),
        )
    except (JobLookupError, ValueError) as e:
        logger.warning("Failed to reschedule morning_brief: %s", e)

    # Reschedule bedtime coaching: 30 min before average bedtime
    bed_hour = timing["bedtime_hour"]
    bed_minute = timing["bedtime_minute"] - 30
    if bed_minute < 0:
        bed_hour = (bed_hour - 1) % 24
        bed_minute += 60

    try:
        scheduler.reschedule_job(
            "bedtime_coaching",
            trigger=CronTrigger(hour=bed_hour, minute=bed_minute, timezone=user_tz),
        )
    except (JobLookupError, ValueError) as e:
        logger.warning("Failed to reschedule bedtime_coaching: %s", e)

    logger.info(
        "Rescheduled: morning_brief=%02d:%02d, bedtime=%02d:%02d",
        wake_hour, wake_minute, bed_hour, bed_minute,
    )


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

    # User-facing notifications run in the user's local timezone (P1-18 fix).
    # Sync jobs and webhook renewal stay in UTC since they're internal.
    from app.config import settings as _settings
    user_tz = _settings.user_timezone

    # Morning brief: 08:00 user-local time
    scheduler.add_job(
        morning_brief_job,
        trigger=CronTrigger(hour=8, minute=0, timezone=user_tz),
        id="morning_brief",
        name="Morning Brief",
        replace_existing=True,
    )

    # Coaching nudge: daily at 12:00 user-local (frequency logic inside job checks preference)
    scheduler.add_job(
        coaching_nudge_job,
        trigger=CronTrigger(hour=12, minute=0, timezone=user_tz),
        id="coaching_nudge",
        name="Coaching Nudge",
        replace_existing=True,
    )

    # Bedtime coaching: daily at 22:00 user-local
    scheduler.add_job(
        bedtime_coaching_job,
        trigger=CronTrigger(hour=22, minute=0, timezone=user_tz),
        id="bedtime_coaching",
        name="Bedtime Coaching",
        replace_existing=True,
    )

    # Streak saver: daily at 18:00 user-local (evening check)
    scheduler.add_job(
        streak_saver_job,
        trigger=CronTrigger(hour=18, minute=0, timezone=user_tz),
        id="streak_saver",
        name="Streak Saver",
        replace_existing=True,
    )

    # Weekly review: Sundays at 18:00 user-local
    scheduler.add_job(
        weekly_review_job,
        trigger=CronTrigger(day_of_week="sun", hour=18, minute=0, timezone=user_tz),
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

    # Peloton sync: every 6 hours
    scheduler.add_job(
        peloton_sync_job,
        trigger=CronTrigger(hour="*/6", minute=30),
        id="peloton_sync",
        name="Peloton Workout Sync",
        replace_existing=True,
    )

    # Garmin sync: every 6 hours
    scheduler.add_job(
        garmin_sync_job,
        trigger=CronTrigger(hour="*/6", minute=45),
        id="garmin_sync",
        name="Garmin Health Sync",
        replace_existing=True,
    )

    # Oura sync: every 30 minutes. Backs up the on-demand sync in
    # health.py's dashboard endpoint — if the user opens the app and has
    # stale data, dashboard sync kicks in; otherwise the scheduler keeps
    # things fresh in the background for webhook/notification jobs that
    # don't go through the dashboard path (e.g. morning_brief_job at 8am
    # needs last-night's sleep already in the DB). Timezone-aware so we
    # fire at consistent wall-clock times regardless of DST.
    from apscheduler.triggers.interval import IntervalTrigger
    scheduler.add_job(
        oura_sync_job,
        trigger=IntervalTrigger(minutes=30),
        id="oura_sync",
        name="Oura Background Sync",
        replace_existing=True,
    )

    # Feature refresh: nightly at 03:30 UTC, before correlation engine runs at
    # 04:00 UTC on Sundays and before user-local morning brief in any timezone.
    # Signal Engine Phase 1 (see ~/.claude/plans/golden-floating-creek.md).
    scheduler.add_job(
        feature_refresh_job,
        trigger=CronTrigger(hour=3, minute=30),
        id="feature_refresh",
        name="Signal Engine Feature Refresh",
        replace_existing=True,
    )

    # Baselines + forecasts + anomalies: nightly at 03:45 UTC, after features
    # land at 03:30. Shadow mode in Phase 2; nothing user-facing reads these
    # rows yet. Plan says Sunday-weekly but daily is cheap and gives fresher
    # forecasts; revisit when prod load demands it.
    scheduler.add_job(
        baselines_job,
        trigger=CronTrigger(hour=3, minute=45),
        id="baselines",
        name="Signal Engine L1 Baselines + Forecasts + Anomalies",
        replace_existing=True,
    )

    # Insight candidates + heuristic ranker: daily at 07:00 user-local, per
    # the Phase 4 plan. Runs after L2 associations (Sunday 04:00 UTC) and L1
    # forecasts (03:45 UTC daily) so candidate generation sees fresh data.
    # Shadow mode: ml_rankings gets populated with was_shown=False until
    # ml_shadow_insight_card is flipped off.
    scheduler.add_job(
        insight_candidate_job,
        trigger=CronTrigger(hour=7, minute=0, timezone=user_tz),
        id="insight_candidate",
        name="Signal Engine Phase 4 Insight Candidates + Ranker",
        replace_existing=True,
    )

    # Correlation engine: weekly Sunday 04:00
    scheduler.add_job(
        correlation_engine_job,
        trigger=CronTrigger(day_of_week="sun", hour=4, minute=0),
        id="correlation_engine",
        name="Cross-Domain Correlation Discovery",
        replace_existing=True,
    )

    # Granger + DoWhy causal: weekly Sunday 04:30 (after correlations finish)
    scheduler.add_job(
        granger_causal_job,
        trigger=CronTrigger(day_of_week="sun", hour=4, minute=30),
        id="granger_causal",
        name="Phase 6 L3 Granger + L4 DoWhy Causal",
        replace_existing=True,
    )

    # Webhook renewal: 1st of each month at 02:00 UTC (90-day TTL, renew monthly)
    scheduler.add_job(
        webhook_renewal_job,
        trigger=CronTrigger(day=1, hour=2, minute=0),
        id="webhook_renewal",
        name="Oura Webhook Renewal",
        replace_existing=True,
    )

    # Timing refresh: daily at 03:00 UTC (recalculates personalized send times)
    scheduler.add_job(
        timing_refresh_job,
        trigger=CronTrigger(hour=3, minute=0),
        id="timing_refresh",
        name="Personalized Timing Refresh",
        replace_existing=True,
    )

    # Offline eval: Sundays at 05:00 UTC (after correlation engine at 04:00)
    scheduler.add_job(
        offline_eval_job,
        trigger=CronTrigger(day_of_week="sun", hour=5, minute=0),
        id="offline_eval",
        name="Weekly Offline Eval",
        replace_existing=True,
    )

    # Synth drift monitor: daily at 04:15 UTC. Sits after feature refresh
    # (03:30), baselines (03:45), and the Sunday correlation_engine slot
    # at 04:00; well before offline eval at 05:00. Short-circuits cleanly
    # when no synth has been generated. Phase 4.5 Commit 5.
    scheduler.add_job(
        synth_drift_job,
        trigger=CronTrigger(hour=4, minute=15),
        id="synth_drift",
        name="Phase 4.5 Synth vs Real Biometric Drift",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Notification scheduler started with %d jobs", len(scheduler.get_jobs()))


def stop_scheduler():
    """Gracefully shut down the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Notification scheduler stopped")
