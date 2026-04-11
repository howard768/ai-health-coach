"""add last_synced_at to oura_tokens

Revision ID: e2b4c9a31f6d
Revises: d1a8e3f4b907
Create Date: 2026-04-11 16:25:00.000000

Adds a `last_synced_at` column to `oura_tokens` so the on-demand dashboard
refresh logic in app/routers/health.py can throttle sync calls by "when did
we last talk to Oura" rather than "when was the newest sleep record saved".

The old check (max SleepRecord.synced_at) was broken: because sync_user_data
skips existing records during dedup, it never bumped synced_at for today's
row after the first successful pull. Every dashboard request older than the
threshold would then keep re-hitting Oura forever even though nothing had
changed, burning rate limit quota.

This column is the single source of truth for "last time we contacted the
Oura API for this user."
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e2b4c9a31f6d"
down_revision: Union[str, Sequence[str], None] = "d1a8e3f4b907"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable so existing rows don't need a backfill — the first sync
    # after deploy will populate it. Downstream code treats NULL as
    # "never synced" which correctly triggers a sync.
    op.add_column(
        "oura_tokens",
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("oura_tokens", "last_synced_at")
