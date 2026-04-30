"""Timezone-safe current-time helpers.

P2-5 fix: `datetime.utcnow()` is deprecated in Python 3.12 and removed in
3.13. It also returned naive datetimes, which silently broke timezone math.

All code that used to call `datetime.utcnow()` should call `utcnow_naive()`
(for columns that still store naive UTC — most of our DB) or `now_utc()`
(for timezone-aware comparisons).

User-facing time helpers (`user_now`, `user_today_iso`, `user_hour`) bind
to `settings.user_timezone` so user-visible logic (meal classification,
date assignment) renders in the user's wall-clock time instead of the
container's UTC. Pre-PR-G, several call sites used `datetime.now()` (naive
local) which is UTC on Railway — every EST user's 8pm dinner was logged
as the next day, and "breakfast" auto-classified at the wrong hour.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def now_utc() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def utcnow_naive() -> datetime:
    """Return the current UTC time as a naive datetime.

    Use for SQLAlchemy columns that store naive UTC timestamps — all of
    ours do, because SQLite doesn't support timezone-aware columns and
    we want consistent behavior across SQLite (dev) and Postgres (prod).

    This is a drop-in replacement for the deprecated `datetime.utcnow()`.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def user_now(tz_name: str | None = None) -> datetime:
    """Return current time as a tz-aware datetime in the user's timezone.

    `tz_name` defaults to `settings.user_timezone` (single-user MVP). When
    multi-user lands, callers should pass the per-user timezone string
    looked up at request scope. Falls back to UTC if the tz name is invalid
    so a typo doesn't crash a user-visible endpoint; the misconfig surfaces
    via `verify_secrets_configured` (PR #90 pattern, future enhancement).
    """
    if tz_name is None:
        # Lazy import to avoid a circular import at module load time.
        from app.config import settings as _settings
        tz_name = _settings.user_timezone

    try:
        tz = ZoneInfo(tz_name)
    except Exception:  # noqa: BLE001 -- fall back rather than crash user request
        tz = timezone.utc
    # Always anchor on UTC and convert; this also makes the function easy
    # to mock in tests via patch("app.core.time.datetime").
    return datetime.now(timezone.utc).astimezone(tz)


def user_today_iso(tz_name: str | None = None) -> str:
    """Return today's date in the user's timezone as 'YYYY-MM-DD'.

    Replaces `datetime.now().strftime("%Y-%m-%d")` which was the broken
    pattern in `routers/meals.py` pre-PR-G. The naive `.now()` returned
    UTC on Railway, so EST users' late-evening meals were dated to the
    next calendar day.
    """
    return user_now(tz_name).strftime("%Y-%m-%d")


def user_hour(tz_name: str | None = None) -> int:
    """Return the current hour (0-23) in the user's timezone.

    Replaces `datetime.now().hour` for any time-of-day classification
    (e.g. meal type breakfast/lunch/snack/dinner).
    """
    return user_now(tz_name).hour
