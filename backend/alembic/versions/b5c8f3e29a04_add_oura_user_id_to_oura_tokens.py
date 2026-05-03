"""add oura_user_id to oura_tokens

Revision ID: b5c8f3e29a04
Revises: a4e9c2b71f08
Create Date: 2026-04-30 21:30:00.000000

Adds a `oura_user_id` column to `oura_tokens` so the webhook receiver in
app/routers/webhooks.py can route incoming events to the correct Meld
user by matching `body["user_id"]` (Oura's user identifier) against the
column.

Pre-PR-MEL-45 the receiver did `select(OuraToken).limit(1)` and routed
ALL incoming Oura events to whatever the first row's user_id was. With
multiple users, the second user's data lands in the first user's row.
This is the audit's #2 multi-user blocker (MEL-43 / MEL-45).

This migration ONLY adds the nullable column. No backfill, no behavior
change. Existing rows get NULL until populated. The next session's PR
will:
  1. Backfill via Oura `/personal_info` API on the next successful sync
  2. Update webhook routing to match on the column (with single-user
     fallback during the transition window)
  3. Update /api/health/canary to return aggregate not user-specific PHI

Tier 3: PHI table (`oura_*` is on the hard-refuse list per CLAUDE.md).
Brock reviews this migration in isolation as a draft PR.

Postgres dialect parity per feedback_postgres_dialect_parity.md: this
migration uses no boolean defaults, no `sa.text("0/1")` traps. ADD
COLUMN with `nullable=True` and no server_default is dialect-neutral.

Rollback: `op.drop_column` is non-destructive (data loss limited to the
oura_user_id values themselves, which can be re-derived from Oura's API
on the next sync).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b5c8f3e29a04"
down_revision: Union[str, Sequence[str], None] = "a4e9c2b71f08"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable so existing rows don't need a backfill at migration time ,
    # the next successful Oura sync per user will populate it. Indexed
    # because the webhook receiver will look up by this column on every
    # incoming event (could be many per minute for multi-user accounts).
    op.add_column(
        "oura_tokens",
        sa.Column("oura_user_id", sa.String(255), nullable=True),
    )
    op.create_index(
        "ix_oura_tokens_oura_user_id",
        "oura_tokens",
        ["oura_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_oura_tokens_oura_user_id", table_name="oura_tokens")
    op.drop_column("oura_tokens", "oura_user_id")
