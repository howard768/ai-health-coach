"""add auth tables and user FKs

Revision ID: c0518b5194eb
Revises: 6edcb0a00c24
Create Date: 2026-04-10 12:13:35.860185

Adds:
1. Auth fields to `users` (is_active, is_private_email, last_login_at, apple_refresh_token)
2. New `refresh_tokens` table for JWT refresh token rotation
3. A 'default' placeholder user so existing tenant rows remain referentially
   valid during FK creation. Data is migrated to real users via a one-shot
   script after Sign in with Apple ships (see backend/app/scripts/claim_default_user.py).
4. FK constraints on all 13 tenant tables → users.apple_user_id

SQLite note: FK changes require `batch_alter_table` because SQLite's ALTER TABLE
is limited. The batch mode recreates the table under a temp name and copies data.
Postgres (Railway prod) doesn't need batch mode but it's harmless.
"""

from typing import Sequence, Union
from datetime import datetime

from alembic import op
import sqlalchemy as sa


revision: str = "c0518b5194eb"
down_revision: Union[str, Sequence[str], None] = "6edcb0a00c24"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Tables that own tenant data and need a FK to users.apple_user_id.
# Keep this list in sync with `app/scripts/claim_default_user.py`.
# food_item_records is intentionally NOT in this list: it has no user_id
# column of its own and inherits tenancy through its meal_id FK to
# meal_records, which IS in this list. Including it here errors on fresh
# Postgres with "column user_id referenced in foreign key constraint does
# not exist" (incident 2026-04-29).
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
]


def upgrade() -> None:
    # ── 1. New columns on users ─────────────────────────────────────────
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true"))
        )
        batch.add_column(
            sa.Column("is_private_email", sa.Boolean(), nullable=False, server_default=sa.text("false"))
        )
        batch.add_column(sa.Column("last_login_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("apple_refresh_token", sa.Text(), nullable=True))

    # ── 2. Create refresh_tokens table ──────────────────────────────────
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.String(length=128), primary_key=True),
        sa.Column("user_id", sa.String(length=255), nullable=False, index=True),
        sa.Column("device_id", sa.String(length=255), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False, index=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("replaced_by", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.apple_user_id"],
            ondelete="CASCADE",
        ),
    )

    # ── 3. Insert the 'default' placeholder user ────────────────────────
    # Existing tenant rows have user_id = 'default'. Without this row, the
    # FK constraints added below would fail the ON-INSERT check. After Sign
    # in with Apple ships, we run a one-shot backfill to reassign data to
    # the real Apple user ID and delete this placeholder.
    now = datetime.utcnow().isoformat(sep=" ", timespec="seconds")
    op.execute(
        f"""
        INSERT INTO users (apple_user_id, is_active, is_private_email, created_at, updated_at)
        SELECT 'default', true, false, '{now}', '{now}'
        WHERE NOT EXISTS (SELECT 1 FROM users WHERE apple_user_id = 'default')
        """
    )

    # ── 4. Add FK constraints on tenant tables ──────────────────────────
    # SQLite requires batch_alter_table for FK changes. This is a no-op on
    # Postgres but still valid SQL.
    for tbl in TENANT_TABLES:
        with op.batch_alter_table(tbl) as batch:
            batch.create_foreign_key(
                f"fk_{tbl}_user",
                "users",
                ["user_id"],
                ["apple_user_id"],
                ondelete="CASCADE",
            )


def downgrade() -> None:
    # Remove FKs first
    for tbl in reversed(TENANT_TABLES):
        with op.batch_alter_table(tbl) as batch:
            batch.drop_constraint(f"fk_{tbl}_user", type_="foreignkey")

    # Drop refresh_tokens table
    op.drop_table("refresh_tokens")

    # Remove new columns from users
    with op.batch_alter_table("users") as batch:
        batch.drop_column("apple_refresh_token")
        batch.drop_column("last_login_at")
        batch.drop_column("is_private_email")
        batch.drop_column("is_active")
