"""One-shot data migration: reassign all 'default' user data to a real Apple user.

After Sign in with Apple ships, run this script ONCE with the operator's real
apple_user_id to migrate the pre-auth data to the real user row.

Usage:
    cd backend
    uv run python -m app.scripts.claim_default_user <target_apple_user_id>

Safety properties:
- Idempotent guard: aborts if 'default' user no longer has data
- Aborts if target user doesn't exist (operator must sign in first)
- Single atomic transaction — all tables updated or none
- Deletes the 'default' placeholder row after migration (preventing re-use)

Rollback: restore from `backend/meld.db.before-auth` or `pg_dump` backup.
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import async_session


# Tenant tables — MUST match the list in the auth Alembic migration
TENANT_TABLES = [
    "oura_tokens",
    "sleep_records",
    "health_metric_records",
    "activity_records",
    "meal_records",
    "chat_messages",
    "conversations",
    "notification_preferences",
    "device_tokens",
    "peloton_tokens",
    "garmin_tokens",
    "user_correlations",
    # food_item_records is tenant-owned by association (via meal_id),
    # not by a direct user_id column — no update needed.
]


async def main(target_apple_id: str) -> int:
    if not target_apple_id or target_apple_id == "default":
        print(f"ERROR: target_apple_id must be a real Apple user ID, not '{target_apple_id}'")
        return 1

    async with async_session() as db:
        # Pre-check 1: 'default' user still exists
        result = await db.execute(
            text("SELECT COUNT(*) FROM users WHERE apple_user_id = 'default'")
        )
        default_count = result.scalar() or 0
        if default_count == 0:
            print("No 'default' user row — nothing to migrate. (Maybe this was already run?)")
            return 0

        # Pre-check 2: target user exists (operator signed in first)
        result = await db.execute(
            text("SELECT COUNT(*) FROM users WHERE apple_user_id = :t"),
            {"t": target_apple_id},
        )
        target_count = result.scalar() or 0
        if target_count == 0:
            print(f"ERROR: Target user '{target_apple_id[:12]}...' not found in users table.")
            print("The operator must complete Sign in with Apple BEFORE running this migration.")
            return 1

        # Pre-check 3: count rows to migrate per table (for the summary log)
        migration_counts: dict[str, int] = {}
        for tbl in TENANT_TABLES:
            try:
                r = await db.execute(
                    text(f"SELECT COUNT(*) FROM {tbl} WHERE user_id = 'default'")
                )
                migration_counts[tbl] = r.scalar() or 0
            except SQLAlchemyError as e:
                print(f"WARN: count failed for {tbl}: {e}")
                migration_counts[tbl] = 0

        total_rows = sum(migration_counts.values())
        print(f"About to migrate {total_rows} rows across {len(TENANT_TABLES)} tables:")
        for tbl, count in migration_counts.items():
            if count > 0:
                print(f"  {tbl}: {count} rows")

        if total_rows == 0:
            print("No data rows owned by 'default'. Just removing the placeholder row.")

        print(f"\nTarget user: {target_apple_id[:12]}...")
        print("Proceeding...\n")

        # Atomic transaction: update all tenant rows, then delete placeholder.
        # Using a single begin() wrapper ensures all-or-nothing semantics.
        async with db.begin_nested() if db.in_transaction() else db.begin():
            for tbl in TENANT_TABLES:
                result = await db.execute(
                    text(f"UPDATE {tbl} SET user_id = :t WHERE user_id = 'default'"),
                    {"t": target_apple_id},
                )
                print(f"  {tbl}: {result.rowcount} rows updated")

            # Delete the placeholder user row
            # CAUTION: this must happen AFTER all tenant updates so the FK CASCADE
            # doesn't wipe data we just reassigned.
            await db.execute(
                text("DELETE FROM users WHERE apple_user_id = 'default'")
            )
            print("  Deleted 'default' placeholder user row")

        await db.commit()
        print(f"\nMigration complete. All data reassigned to {target_apple_id[:12]}...")
        return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: uv run python -m app.scripts.claim_default_user <apple_user_id>")
        sys.exit(1)
    exit_code = asyncio.run(main(sys.argv[1]))
    sys.exit(exit_code)
