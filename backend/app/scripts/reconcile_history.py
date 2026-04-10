"""One-shot: run reconcile_day for every date that has health data.

The reconciliation job normally runs daily for today only. This script
backfills canonical flags for all historical dates, which is required
after the data migration so the dashboard can read historical sleep data.

Usage:
    cd backend
    uv run python -m app.scripts.reconcile_history <apple_user_id>
"""

import asyncio
import sys

from sqlalchemy import select, distinct

from app.database import async_session
from app.models.health import HealthMetricRecord
from app.services.data_reconciliation import reconcile_day


async def main(user_id: str) -> int:
    async with async_session() as db:
        # Find every distinct date with data for this user
        result = await db.execute(
            select(distinct(HealthMetricRecord.date))
            .where(HealthMetricRecord.user_id == user_id)
            .order_by(HealthMetricRecord.date)
        )
        dates = [row[0] for row in result.all()]

    if not dates:
        print(f"No health data found for user {user_id[:12]}...")
        return 1

    print(f"Reconciling {len(dates)} dates for {user_id[:12]}...")
    for date_str in dates:
        async with async_session() as db:
            canonical = await reconcile_day(db, user_id, date_str)
            print(f"  {date_str}: {len(canonical)} metrics canonical")

    print("Done.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: uv run python -m app.scripts.reconcile_history <apple_user_id>")
        sys.exit(1)
    exit_code = asyncio.run(main(sys.argv[1]))
    sys.exit(exit_code)
