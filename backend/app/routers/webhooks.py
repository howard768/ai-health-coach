"""Webhook receiver endpoints.

Handles incoming webhooks from Oura (and future data sources).
When Oura sends a webhook, we trigger a sync + coaching notification.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Request, Query, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.oura_sync import sync_user_data
from app.services.oura_webhooks import (
    WEBHOOK_VERIFICATION_TOKEN,
    register_all_webhooks,
    list_subscriptions,
)

from app.api.deps import CurrentUser

logger = logging.getLogger("meld.webhooks")

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.get("/oura")
async def oura_webhook_verification(
    verification_token: str = Query(None),
    challenge: str = Query(None),
):
    """Oura webhook verification handshake.

    Oura sends GET with verification_token + challenge.
    We verify the token matches ours, then echo back the challenge.
    """
    if verification_token == WEBHOOK_VERIFICATION_TOKEN and challenge:
        logger.info("Oura webhook verification successful, challenge=%s", challenge)
        # Oura expects JSON response with the challenge value
        return {"challenge": challenge}
    logger.warning("Oura webhook verification failed — token=%s challenge=%s", verification_token, challenge)
    return {"error": "Invalid verification"}


@router.post("/oura")
async def oura_webhook_receiver(request: Request, db: AsyncSession = Depends(get_db)):
    """Receive Oura webhook events.

    Oura POSTs here when new data is available (sleep, readiness, activity, etc.).
    Oura does not send bearer auth, so we validate via:
      1. Body shape — must have `event_type`, `data_type`, and `user_id`
      2. The handler does NOT trust webhook body content for health data — it
         re-fetches everything from Oura's API using our OAuth token. A forged
         webhook can only cause an unnecessary sync, not poison data.
      3. Per-user-per-minute throttle — caps the damage of a webhook flood.

    TODO (multi-user): add `oura_user_id` column to OuraToken and match on
    `body["user_id"]` to route events to the correct Meld user.
    """
    try:
        body = await request.json()
    except Exception:
        logger.warning("Oura webhook received invalid JSON")
        return {"status": "invalid_payload"}

    event_type = body.get("event_type")
    data_type = body.get("data_type")
    user_oura_id = body.get("user_id")
    timestamp = body.get("timestamp")

    # Body shape validation — Oura always sends these fields
    if not event_type or not data_type or not user_oura_id:
        logger.warning(
            "Oura webhook missing required fields: event=%s data=%s user=%s",
            event_type, data_type, user_oura_id,
        )
        return {"status": "invalid_payload"}

    logger.info(
        "Oura webhook: event=%s data=%s user=%s time=%s",
        event_type, data_type, user_oura_id, timestamp,
    )

    # Per-user throttle: at most 1 sync per 60s regardless of webhook count.
    # Prevents a webhook flood from exhausting Oura API quota or Claude budget.
    # In-memory store is fine for single-instance Railway deploy.
    from datetime import datetime, timedelta
    if not hasattr(oura_webhook_receiver, "_last_sync_at"):
        oura_webhook_receiver._last_sync_at = {}  # type: ignore[attr-defined]
    last_sync_map = oura_webhook_receiver._last_sync_at  # type: ignore[attr-defined]
    last = last_sync_map.get(user_oura_id)
    now = datetime.utcnow()
    if last and (now - last) < timedelta(seconds=60):
        logger.info("Oura webhook throttled (last sync %ds ago)", (now - last).seconds)
        return {"status": "throttled"}
    last_sync_map[user_oura_id] = now

    # MVP: find the user who owns an Oura token. In multi-user mode we would
    # match on the Oura user ID from the webhook body.
    from app.models.health import OuraToken
    from sqlalchemy import select
    token_result = await db.execute(select(OuraToken).limit(1))
    token = token_result.scalar_one_or_none()
    if not token:
        logger.warning("Oura webhook received but no users have connected Oura — ignoring")
        return {"status": "no_user"}
    meld_user_id = token.user_id

    # Trigger sync to pull latest data. Return 200 even on sync failure so
    # Oura doesn't retry — their retry budget is scarce and a failed sync
    # will be picked up by the scheduled job within 6 hours. P2-16.
    try:
        result = await sync_user_data(db, meld_user_id)
        logger.info("Webhook-triggered sync: %s", result)
    except Exception as e:
        logger.error("Webhook sync failed (returning 200 to Oura): %s", e)
        return {"status": "sync_failed", "error": str(e)}

    # If this is a readiness update, trigger the morning brief notification
    if data_type == "daily_readiness" and event_type in ("create", "update"):
        try:
            from app.services.notification_engine import notification_engine
            from app.services.apns import apns_client
            from app.models.notification import DeviceToken
            from app.models.health import SleepRecord
            from app.models.user import User
            from sqlalchemy import desc

            # Load user for personalized greeting
            user_result = await db.execute(
                select(User).where(User.apple_user_id == meld_user_id)
            )
            user = user_result.scalar_one_or_none()
            user_name = (user.name.split()[0] if user and user.name else "there")

            # Get latest health data
            sleep_result = await db.execute(
                select(SleepRecord)
                .where(SleepRecord.user_id == meld_user_id)
                .order_by(desc(SleepRecord.date))
                .limit(1)
            )
            sr = sleep_result.scalar_one_or_none()
            if sr:
                health_data = {
                    "sleep_efficiency": sr.efficiency,
                    "hrv_average": sr.hrv_average,
                    "resting_hr": sr.resting_hr,
                    "readiness_score": sr.readiness_score,
                    "total_sleep_hours": (sr.total_sleep_seconds or 0) / 3600,
                }

                # Generate morning brief
                content = notification_engine.generate_morning_brief(
                    health_data, user_name=user_name
                )

                # Send push notification
                token_result = await db.execute(
                    select(DeviceToken).where(
                        DeviceToken.user_id == meld_user_id,
                        DeviceToken.is_active == True,
                        DeviceToken.token != "test_token_abc123",
                    )
                )
                for token_row in token_result.scalars().all():
                    await apns_client.send_push(
                        device_token=token_row.token,
                        title=content["title"],
                        body=content["body"],
                        category=content["apns"]["category"],
                        thread_id=content["apns"]["thread_id"],
                        interruption_level="time-sensitive",
                        relevance_score=1.0,
                        data=content["data"],
                        media_url=content.get("media_url"),
                    )
                    logger.info("Webhook-triggered morning brief sent")

        except Exception as e:
            logger.error("Failed to send webhook-triggered notification: %s", e)

    return {"status": "ok"}


# ── Admin Endpoints ─────────────────────────────────────────

@router.post("/oura/register")
async def register_webhooks(
    current_user: CurrentUser,
    base_url: str = Query(...),
):
    """Register all Oura webhook subscriptions.

    Call once with your public backend URL:
    POST /api/webhooks/oura/register?base_url=https://your-domain.com

    Auth-gated to prevent attackers redirecting your webhooks to their servers (P1-3).
    """
    # Validate base_url is one of our known domains to prevent SSRF-style abuse
    allowed_prefixes = (
        "http://localhost",
        "http://192.168.",
        "https://zippy-forgiveness-production-0704.up.railway.app",
    )
    if not any(base_url.startswith(p) for p in allowed_prefixes):
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail=f"base_url must start with one of: {allowed_prefixes}",
        )

    results = await register_all_webhooks(base_url)
    return {"status": "ok", "subscriptions": len(results), "details": results}


@router.get("/oura/subscriptions")
async def get_subscriptions(current_user: CurrentUser):
    """List all active Oura webhook subscriptions (admin endpoint)."""
    try:
        subs = await list_subscriptions()
        return {"subscriptions": subs}
    except Exception as e:
        return {"error": str(e)}
