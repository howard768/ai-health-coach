"""add waitlist_signups table

Revision ID: d1a8e3f4b907
Revises: c0518b5194eb
Create Date: 2026-04-11 15:45:00.000000

Adds the `waitlist_signups` table to capture pre-launch email signups from
heymeld.com. This is separate from `users` — these are cold leads (email +
campaign metadata), not authenticated tenants.

Dedupe key: lowercased `email` column with a unique index. Re-submissions
touch `updated_at` and increment `submissions` rather than creating dupes.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d1a8e3f4b907"
down_revision: Union[str, Sequence[str], None] = "c0518b5194eb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "waitlist_signups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("utm_source", sa.String(length=128), nullable=True),
        sa.Column("utm_medium", sa.String(length=128), nullable=True),
        sa.Column("utm_campaign", sa.String(length=128), nullable=True),
        sa.Column("utm_term", sa.String(length=128), nullable=True),
        sa.Column("utm_content", sa.String(length=128), nullable=True),
        sa.Column("referer", sa.String(length=512), nullable=True),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("notified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("submissions", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_waitlist_signups_email",
        "waitlist_signups",
        ["email"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_waitlist_signups_email", table_name="waitlist_signups")
    op.drop_table("waitlist_signups")
