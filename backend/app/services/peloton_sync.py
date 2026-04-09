"""Peloton data sync service.

Follows the same pattern as oura_sync.py:
ensure_valid_session → sync_user_data → write to WorkoutRecord + HealthMetricRecord.
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.peloton import PelotonToken, WorkoutRecord
from app.models.health import HealthMetricRecord
from app.services.peloton import PelotonClient

logger = logging.getLogger("meld.peloton_sync")


async def ensure_valid_session(db: AsyncSession, user_id: str) -> tuple[str, str] | None:
    """Get valid Peloton session. Returns (session_id, peloton_user_id) or None."""
    result = await db.execute(
        select(PelotonToken)
        .where(PelotonToken.user_id == user_id)
        .order_by(desc(PelotonToken.created_at))
        .limit(1)
    )
    token = result.scalar_one_or_none()
    if not token:
        return None

    # Peloton sessions don't have explicit expiration — they just stop working
    # We'll detect 401 during sync and prompt re-login
    return (token.session_id, token.peloton_user_id)


async def sync_user_data(db: AsyncSession, user_id: str) -> dict:
    """Sync Peloton workout data for a user."""
    session_info = await ensure_valid_session(db, user_id)
    if not session_info:
        return {"status": "error", "message": "No Peloton session. Connect your account."}

    session_id, peloton_user_id = session_info
    client = PelotonClient(session_id=session_id, user_id=peloton_user_id)

    try:
        workouts_response = await client.get_workouts(limit=20)
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg:
            return {"status": "error", "message": "Peloton session expired. Please re-login."}
        logger.error("Peloton API error: %s", e)
        return {"status": "error", "message": f"Peloton API error: {error_msg}"}

    records_saved = 0
    for workout in workouts_response.get("data", []):
        parsed = client.parse_workout(workout)
        workout_id = parsed.get("peloton_workout_id")

        # Dedup by external_id
        existing = await db.execute(
            select(WorkoutRecord).where(
                WorkoutRecord.user_id == user_id,
                WorkoutRecord.external_id == workout_id,
                WorkoutRecord.source == "peloton",
            )
        )
        if existing.scalar_one_or_none():
            continue

        # Convert timestamp to date
        created_at = parsed.get("created_at", 0)
        workout_date = datetime.utcfromtimestamp(created_at).strftime("%Y-%m-%d") if created_at else datetime.utcnow().strftime("%Y-%m-%d")

        record = WorkoutRecord(
            user_id=user_id,
            date=workout_date,
            source="peloton",
            external_id=workout_id,
            workout_type=parsed["workout_type"],
            duration_seconds=parsed["duration_seconds"],
            calories=parsed.get("calories"),
            avg_heart_rate=parsed.get("avg_heart_rate"),
            max_heart_rate=parsed.get("max_heart_rate"),
            avg_output=parsed.get("avg_output"),
            instructor=parsed.get("instructor"),
            title=parsed.get("title"),
            raw_json=str(workout),
        )
        db.add(record)

        # Also write to unified HealthMetricRecord for reconciliation
        if parsed["duration_seconds"]:
            db.add(HealthMetricRecord(
                user_id=user_id, date=workout_date,
                metric_type="workouts", value=parsed["duration_seconds"] / 60,
                unit="minutes", source="peloton",
            ))
        if parsed.get("calories"):
            db.add(HealthMetricRecord(
                user_id=user_id, date=workout_date,
                metric_type="active_calories", value=parsed["calories"],
                unit="kcal", source="peloton",
            ))

        records_saved += 1

    await db.commit()

    result = {"status": "ok", "records_saved": records_saved}
    logger.info("Peloton sync complete: %s", result)
    return result
