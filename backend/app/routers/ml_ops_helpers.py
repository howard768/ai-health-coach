"""Small pure helpers shared by ml_ops endpoints.

Extracted from ml_ops.py per docs/comprehensive-scan-2026-04-30.md
recommendation 19 (god-module split). The router file owns the routes;
this module owns the timestamp + scalar-fetch utilities used by every
endpoint.

No business logic here. Only datatype normalization and the one async
SELECT-and-scalar wrapper used to defend against missing tables.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _iso(value: Any) -> str | None:
    """Normalize a DB timestamp to ISO-8601 with a ``T`` separator.

    SQLite returns DateTime values as strings with a space separator; Postgres
    returns ``datetime`` objects. Normalize both so downstream JSON consumers
    never have to branch.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    s = str(value)
    if len(s) >= 11 and s[10] == " ":
        s = s[:10] + "T" + s[11:]
    return s


def _days_between(iso_ts: str | None, now: datetime) -> int | None:
    """Return whole days between an ISO timestamp and ``now``, or None."""
    if not iso_ts:
        return None
    try:
        s = iso_ts.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(s)
        # Strip tz so we can diff against a naive reference if needed.
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        ref = now.replace(tzinfo=None) if now.tzinfo else now
        return max(0, (ref - parsed).days)
    except Exception:
        return None


async def _scalar_or_none(db: AsyncSession, sql: str, **params: Any) -> Any:
    """Run a SELECT and return the first scalar, or None on any failure."""
    try:
        row = await db.execute(text(sql), params)
        return row.scalar()
    except Exception:
        await db.rollback()
        return None
