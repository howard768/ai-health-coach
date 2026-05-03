"""add onboarding_complete to users

Revision ID: f3a1d8c92e05
Revises: e2b4c9a31f6d
Create Date: 2026-04-11 18:00:00.000000

Adds `onboarding_complete` boolean to the users table so the backend can
tell reinstalled clients whether this account has already been through
onboarding. The iOS app reads this on first-launch after reinstall and
hydrates the local `hasCompletedOnboarding` AppStorage flag from it,
preventing a second onboarding pass for returning users.

Existing rows default to False, they will be set to True the next time
the user's client calls PUT /api/user/profile with onboarding_complete=true
(which happens at the end of the FirstSync step).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f3a1d8c92e05"
down_revision: Union[str, Sequence[str], None] = "e2b4c9a31f6d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("onboarding_complete", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("users", "onboarding_complete")
