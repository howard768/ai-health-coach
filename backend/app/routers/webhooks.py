"""Webhook receiver endpoints.

Handles incoming webhooks from Oura (and future data sources).
When Oura sends a webhook, we trigger a sync + coaching notification.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Request, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.oura_sync import sync_user_data
from app.services.oura_webhooks import (
    WEBHOOK_VERIFICATION_TOKEN,
    register_all_webhooks,
    list_subscriptions,
)

logger = logging.getLogger("meld.webhooks")

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

USER_ID = "default"  # TODO: replace with real auth


@router.get("/oura")
async def oura_webhook_verification(verification_token: str = Query(None)):
    """Oura webhook verification handshake.

    When registering a webhook, Oura sends a GET request to verify
    the callback URL. We must echo back the verification_token.
    """
    if verification_token == WEBHOOK_VERIFICATION_TOKEN:
        logger.info("Oura webhook verification successful")
        return verification_token
    logger.warning("Oura webhook verification failed — token mismatch")
    return {"error": "Invalid verification token"}


@router.post("/oura")
async def oura_webhook_receiver(request: Request, db: AsyncSession = Depends(get_db)):
    """Receive Oura webhook events.

    Oura POSTs here when new data is available (sleep, readiness, activity, etc.).
    We trigger a sync to pull the latest data and optionally send a coaching notification.
    """
    body = await request.json()
    event_type = body.get("event_type")
    data_type = body.get("data_type")
    user_oura_id = body.get("user_id")
    timestamp = body.get("timestamp")

    logger.info(
        "Oura webhook: event=%s data=%s user=%s time=%s",
        event_type, data_type, user_oura_id, timestamp,
    )

    # Trigger sync to pull latest data
    result = await sync_user_data(db, USER_ID)
    logger.info("Webhook-triggered sync: %s", result)

    # If this is a readiness update, trigger the morning brief notification
    if data_type == "daily_readiness" and event_type in ("create", "update"):
        try:
            from app.services.notification_engine import notification_engine
            from app.services.apns import apns_client
            from app.models.notification import DeviceToken
            from app.models.health import SleepRecord
            from sqlalchemy import select, desc

            # Get latest health data
            sleep_result = await db.execute(
                select(SleepRecord)
                .where(SleepRecord.user_id == USER_ID)
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
                    health_data, user_name="Brock"
                )

                # Send push notification
                token_result = await db.execute(
                    select(DeviceToken).where(
                        DeviceToken.user_id == USER_ID,
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
async def register_webhooks(base_url: str = Query(...)):
    """Register all Oura webhook subscriptions.

    Call once with your public backend URL:
    POST /api/webhooks/oura/register?base_url=https://your-domain.com
    """
    results = await register_all_webhooks(base_url)
    return {"status": "ok", "subscriptions": len(results), "details": results}


@router.get("/oura/subscriptions")
async def get_subscriptions():
    """List all active Oura webhook subscriptions."""
    try:
        subs = await list_subscriptions()
        return {"subscriptions": subs}
    except Exception as e:
        return {"error": str(e)}
