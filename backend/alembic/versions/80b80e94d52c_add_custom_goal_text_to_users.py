"""add custom_goal_text to users

Revision ID: 80b80e94d52c
Revises: b384bb88217f
Create Date: 2026-04-16 22:23:15.679684

Adds `custom_goal_text` to the users table so the free-form "what do you
want to get out of this?" answer on the onboarding Goals step actually
persists instead of dying in the iOS view model (build 3-5 bug, reported
in Brock's 2026-04-16 beta feedback: "still doesn't do anything when I
input my free text").

Backfill: nullable. Existing users remain at NULL until they re-open the
Goals step or edit the field in Profile settings.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '80b80e94d52c'
down_revision: Union[str, Sequence[str], None] = 'b384bb88217f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("custom_goal_text", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "custom_goal_text")
