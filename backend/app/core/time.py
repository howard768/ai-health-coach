"""Timezone-safe current-time helpers.

P2-5 fix: `datetime.utcnow()` is deprecated in Python 3.12 and removed in
3.13. It also returned naive datetimes, which silently broke timezone math.

All code that used to call `datetime.utcnow()` should call `utcnow_naive()`
(for columns that still store naive UTC — most of our DB) or `now_utc()`
(for timezone-aware comparisons).
"""

from datetime import datetime, timezone


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
