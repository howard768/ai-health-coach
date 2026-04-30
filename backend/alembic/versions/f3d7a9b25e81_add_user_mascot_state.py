"""add user_mascot_state table

Revision ID: f3d7a9b25e81
Revises: e2b4c9a31f6d
Create Date: 2026-04-11 19:00:00.000000

Adds the `user_mascot_state` table to track which mascot accessories each
user has unlocked and equipped. Backs the customization system that lets
users earn things (Armothy muscle arms, pounding heart, shield, etc.) as
they hit usage milestones.

One row per (user_id, accessory_id) pair. Unlock is permanent; equip is
toggleable. Multiple accessories can be equipped at once. The `accessory_id`
is an opaque client-side string — the iOS `MascotAccessory` enum is the
source of truth for the catalog, the backend just tracks state.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f3d7a9b25e81"
down_revision: Union[str, Sequence[str], None] = "e2b4c9a31f6d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_mascot_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("accessory_id", sa.String(length=64), nullable=False),
        sa.Column(
            "unlocked_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "equipped",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.UniqueConstraint(
            "user_id", "accessory_id", name="uq_user_mascot_accessory"
        ),
    )
    op.create_index(
        "ix_user_mascot_state_user_id",
        "user_mascot_state",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_user_mascot_state_user_id", table_name="user_mascot_state")
    op.drop_table("user_mascot_state")
