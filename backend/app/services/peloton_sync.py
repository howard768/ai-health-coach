"""Peloton data sync service.

MEL-44 part 2: re-enable scheduled syncs by logging in fresh on every call.

Architecture
------------
Peloton has no OAuth and `pylotoncycle` does not expose a persistable session
token, so the only way to keep syncing on a schedule is to hold the user's
credentials at rest and re-authenticate per cycle. PR #103 added the encrypted
`PelotonToken.password` column. Here we:

1. Look up the user's PelotonToken (most recent row).
2. Decrypt + read username + password (EncryptedString TypeDecorator).
3. `client.login(username, password)` — fresh PylotonCycle instance per sync.
4. On login failure (password rotated, account suspended, network glitch),
   return a structured `needs_reauth` status and capture to Sentry. The
   scheduler logs this without alerting; the iOS client surfaces a
   "Reconnect Peloton" CTA in Settings.
5. On success: fetch recent workouts, dedup by external_id, write
   WorkoutRecord + HealthMetricRecord, update token.last_used_at.

The legacy `session_id="oauth"` placeholder is kept on the row for the
NOT-NULL constraint but is no longer read. The token row exists purely to
hold (username, encrypted_password, peloton_user_id, last_used_at).
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow_naive
from app.models.health import HealthMetricRecord
from app.models.peloton import PelotonToken, WorkoutRecord
from app.services.peloton import PelotonClient, _PELOTON_FETCH_ERRORS

logger = logging.getLogger("meld.peloton_sync")


async def _load_token(db: AsyncSession, user_id: str) -> PelotonToken | None:
    """Fetch the most recent PelotonToken row for this user."""
    result = await db.execute(
        select(PelotonToken)
        .where(PelotonToken.user_id == user_id)
        .order_by(desc(PelotonToken.created_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


def _capture_reauth_needed(user_id: str, reason: str, exc: BaseException | None = None) -> None:
    """Best-effort Sentry capture so we have a signal when users start failing
    auth at scale (eg. Peloton rotates client tokens, breaks pylotoncycle)."""
    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            scope.set_tag("peloton_action", "needs_reauth")
            scope.set_extra("user_id_prefix", user_id[:12] if user_id else None)
            scope.set_extra("reason", reason)
            if exc is not None:
                scope.set_extra("error", str(exc))
            sentry_sdk.capture_message(
                "Peloton sync failed: needs reauth",
                level="warning",
            )
    except Exception:  # noqa: BLE001 -- never let Sentry crash the sync handler
        logger.debug("Sentry capture failed (non-fatal)", exc_info=True)


async def sync_user_data(db: AsyncSession, user_id: str) -> dict:
    """Sync recent Peloton workouts for a user.

    Returns one of:
      - {"status": "no_session", ...}      no PelotonToken row exists
      - {"status": "needs_reauth", ...}    creds present but login failed
      - {"status": "ok", "records_saved": N}
    """
    token = await _load_token(db, user_id)
    if token is None:
        return {"status": "no_session", "message": "No Peloton session. Connect your account."}

    if not token.password or not token.username:
        # Legacy row from before the password column landed (pre-MEL-44 part 1)
        # — user must reconnect so we can capture credentials.
        _capture_reauth_needed(user_id, reason="missing_credentials_legacy_row")
        return {
            "status": "needs_reauth",
            "message": "Peloton needs reconnection to enable scheduled syncs.",
        }

    client = PelotonClient()
    try:
        await client.login(token.username, token.password)
    except _PELOTON_FETCH_ERRORS as e:
        logger.warning(
            "Peloton login failed for user %s: %s. Marking needs_reauth.",
            user_id[:12], e,
        )
        _capture_reauth_needed(user_id, reason="login_failed", exc=e)
        return {
            "status": "needs_reauth",
            "message": "Peloton login failed. Please reconnect.",
        }
    except ImportError:
        logger.error("pylotoncycle not installed; cannot sync Peloton")
        return {"status": "error", "message": "pylotoncycle package not installed"}

    # pylotoncycle's GetRecentWorkouts returns a LIST of workout dicts, not a
    # dict. The pre-deferral code that called .get("data", []) on the result
    # was always going to AttributeError if it ever ran.
    try:
        workouts = await client.get_workouts(limit=20)
    except _PELOTON_FETCH_ERRORS as e:
        logger.error("Peloton get_workouts failed for user %s: %s", user_id[:12], e)
        return {"status": "error", "message": f"Peloton API error: {e}"}

    if not isinstance(workouts, list):
        # Defensive: if pylotoncycle ever changes return shape, log + bail.
        logger.error(
            "Peloton get_workouts returned %s, expected list — bailing", type(workouts)
        )
        return {"status": "error", "message": "unexpected Peloton response shape"}

    records_saved = 0
    for raw in workouts:
        if not isinstance(raw, dict):
            continue
        parsed = client.parse_workout(raw)
        external_id = parsed.get("peloton_workout_id")
        if not external_id:
            continue

        # Dedup by (user_id, source, external_id)
        existing_q = await db.execute(
            select(WorkoutRecord).where(
                WorkoutRecord.user_id == user_id,
                WorkoutRecord.external_id == external_id,
                WorkoutRecord.source == "peloton",
            )
        )
        if existing_q.scalar_one_or_none():
            continue

        # Convert Peloton's epoch timestamp -> YYYY-MM-DD (UTC)
        created_at_epoch = parsed.get("created_at") or 0
        if created_at_epoch:
            workout_date = datetime.fromtimestamp(created_at_epoch, tz=timezone.utc).strftime(
                "%Y-%m-%d"
            )
        else:
            workout_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        db.add(
            WorkoutRecord(
                user_id=user_id,
                date=workout_date,
                source="peloton",
                external_id=external_id,
                workout_type=parsed["workout_type"],
                duration_seconds=parsed["duration_seconds"],
                calories=parsed.get("calories"),
                avg_heart_rate=parsed.get("avg_heart_rate"),
                max_heart_rate=parsed.get("max_heart_rate"),
                avg_output=parsed.get("avg_output"),
                instructor=parsed.get("instructor"),
                title=parsed.get("title"),
                raw_json=str(raw),
            )
        )

        # Mirror into the unified HealthMetricRecord stream so reconciliation
        # picks up Peloton calories + minutes alongside HealthKit + Garmin.
        if parsed.get("duration_seconds"):
            db.add(
                HealthMetricRecord(
                    user_id=user_id,
                    date=workout_date,
                    metric_type="workouts",
                    value=parsed["duration_seconds"] / 60.0,
                    unit="minutes",
                    source="peloton",
                )
            )
        if parsed.get("calories"):
            db.add(
                HealthMetricRecord(
                    user_id=user_id,
                    date=workout_date,
                    metric_type="active_calories",
                    value=parsed["calories"],
                    unit="kcal",
                    source="peloton",
                )
            )

        records_saved += 1

    # Update last_used_at so we know syncs are landing
    token.last_used_at = utcnow_naive()
    await db.commit()

    logger.info(
        "Peloton sync complete for user %s: %d new workouts saved",
        user_id[:12], records_saved,
    )
    return {"status": "ok", "records_saved": records_saved}
