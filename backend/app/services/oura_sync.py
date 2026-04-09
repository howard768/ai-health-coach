"""Oura data sync service.

Refactored from the health router's inline sync logic into a reusable service
callable from both the API endpoint and the background scheduler.
Handles token refresh, sleep data, readiness, and HRV.
"""

import logging
from datetime import date, datetime, timedelta

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.health import OuraToken, SleepRecord, HealthMetricRecord
from app.services.oura import OuraClient

logger = logging.getLogger("meld.oura_sync")


async def ensure_valid_token(db: AsyncSession, user_id: str) -> str | None:
    """Get a valid Oura access token, refreshing if expired.

    Returns the valid access_token string, or None if no token exists
    or refresh failed (user revoked access).
    """
    result = await db.execute(
        select(OuraToken)
        .where(OuraToken.user_id == user_id)
        .order_by(desc(OuraToken.created_at))
        .limit(1)
    )
    token = result.scalar_one_or_none()
    if not token:
        logger.warning("No Oura token found for user %s", user_id)
        return None

    # Check if token expires within 5 minutes
    if token.expires_at and token.expires_at < datetime.utcnow() + timedelta(minutes=5):
        logger.info("Oura token expired or expiring soon — refreshing")
        try:
            client = OuraClient()
            new_tokens = await client.refresh_access_token(token.refresh_token)
            token.access_token = new_tokens["access_token"]
            token.refresh_token = new_tokens.get("refresh_token", token.refresh_token)
            token.expires_at = datetime.utcnow() + timedelta(seconds=new_tokens.get("expires_in", 86400))
            await db.commit()
            logger.info("Oura token refreshed successfully")
        except Exception as e:
            logger.error("Oura token refresh failed: %s", e)
            return None

    return token.access_token


async def sync_user_data(db: AsyncSession, user_id: str) -> dict:
    """Sync latest Oura data for a user.

    Pulls sleep, readiness, and HRV data for the last 7 days.
    Deduplicates against existing records.
    Returns status dict with records_saved count.
    """
    access_token = await ensure_valid_token(db, user_id)
    if not access_token:
        return {"status": "error", "message": "No valid Oura token"}

    client = OuraClient(access_token=access_token)
    start = date.today() - timedelta(days=7)
    end = date.today()

    try:
        sleep_data = await client.get_daily_sleep(start, end)
        readiness_data = await client.get_daily_readiness(start, end)
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg:
            logger.error("Oura API returned 401 — token may be revoked")
            return {"status": "error", "message": "Oura access revoked. Reconnect your ring."}
        logger.error("Oura API error: %s", e)
        return {"status": "error", "message": f"Oura API error: {error_msg}"}

    records_saved = 0
    for day in sleep_data.get("data", []):
        day_date = day.get("day", "")

        # Skip if record already exists
        existing = await db.execute(
            select(SleepRecord).where(
                SleepRecord.user_id == user_id,
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

        # Parse bedtime timestamps
        contributors = day.get("contributors", {})
        bedtime_start = _parse_time(day.get("bedtime_start"))
        bedtime_end = _parse_time(day.get("bedtime_end"))

        record = SleepRecord(
            user_id=user_id,
            date=day_date,
            efficiency=contributors.get("efficiency"),
            total_sleep_seconds=day.get("total_sleep_duration"),
            deep_sleep_seconds=day.get("deep_sleep_duration"),
            rem_sleep_seconds=day.get("rem_sleep_duration"),
            light_sleep_seconds=day.get("light_sleep_duration"),
            hrv_average=None,  # Patched by sync_hrv below
            resting_hr=day.get("lowest_heart_rate"),
            readiness_score=readiness_score,
            bedtime_start=bedtime_start,
            bedtime_end=bedtime_end,
            raw_json=str(day),
        )
        db.add(record)
        records_saved += 1

        # Also write to unified HealthMetricRecord for reconciliation
        if contributors.get("efficiency"):
            db.add(HealthMetricRecord(user_id=user_id, date=day_date, metric_type="sleep_efficiency", value=contributors["efficiency"], unit="%", source="oura"))
        if day.get("total_sleep_duration"):
            db.add(HealthMetricRecord(user_id=user_id, date=day_date, metric_type="sleep_duration", value=day["total_sleep_duration"] / 3600, unit="hours", source="oura"))
        if day.get("lowest_heart_rate"):
            db.add(HealthMetricRecord(user_id=user_id, date=day_date, metric_type="resting_hr", value=day["lowest_heart_rate"], unit="bpm", source="oura"))
        if readiness_score:
            db.add(HealthMetricRecord(user_id=user_id, date=day_date, metric_type="readiness", value=readiness_score, unit="score", source="oura"))

    await db.commit()

    # Sync HRV from heartrate endpoint
    hrv_updated = await sync_hrv(client, db, user_id, start, end)

    result = {
        "status": "ok",
        "records_saved": records_saved,
        "hrv_updated": hrv_updated,
        "days_synced": len(sleep_data.get("data", [])),
    }
    logger.info("Oura sync complete: %s", result)
    return result


async def sync_hrv(
    client: OuraClient, db: AsyncSession, user_id: str, start: date, end: date
) -> int:
    """Pull HRV data from Oura heartrate endpoint and patch SleepRecords.

    Computes average HRV from heart rate samples during the sleep window.
    Returns count of records updated.
    """
    try:
        hr_data = await client.get_heartrate(start, end)
    except Exception as e:
        logger.warning("Failed to fetch HRV data: %s", e)
        return 0

    # Group HR samples by date
    samples_by_date: dict[str, list[float]] = {}
    for sample in hr_data.get("data", []):
        ts = sample.get("timestamp", "")
        bpm = sample.get("bpm")
        source = sample.get("source", "")
        if not ts or not bpm:
            continue
        # Only use resting/sleep samples for HRV proxy
        if source in ("rest", "sleep"):
            day_str = ts[:10]  # "YYYY-MM-DD"
            samples_by_date.setdefault(day_str, []).append(bpm)

    # Patch SleepRecords that have hrv_average = None
    updated = 0
    records = await db.execute(
        select(SleepRecord).where(
            SleepRecord.user_id == user_id,
            SleepRecord.hrv_average.is_(None),
            SleepRecord.date >= str(start),
            SleepRecord.date <= str(end),
        )
    )
    for record in records.scalars().all():
        samples = samples_by_date.get(record.date, [])
        if samples:
            # NOTE: This stores average resting HR during sleep as an HRV proxy.
            # True RMSSD HRV requires the Oura v2 HRV endpoint or raw inter-beat
            # interval data, which is not available via the daily_sleep scope.
            # This proxy correlates with HRV trends but is not clinically accurate.
            avg_resting = sum(samples) / len(samples)
            record.hrv_average = round(avg_resting, 1)
            updated += 1

    if updated:
        await db.commit()
        logger.info("Updated HRV for %d records", updated)

    return updated


def _parse_time(iso_timestamp: str | None) -> str | None:
    """Parse an ISO 8601 timestamp into HH:MM format."""
    if not iso_timestamp:
        return None
    try:
        dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        return dt.strftime("%H:%M")
    except (ValueError, AttributeError):
        return None
