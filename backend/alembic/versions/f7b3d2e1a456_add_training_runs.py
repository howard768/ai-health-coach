"""Add ml_training_runs table and rolled_back_at column

Revision ID: f7b3d2e1a456
Revises: e6a2b4c8d901
Create Date: 2026-04-16 (Signal Engine Phase 10 Commit 2/3)

Adds ``rolled_back_at`` to ``ml_models`` for rollback audit trail.
Creates ``ml_training_runs`` table for lightweight experiment tracking
(alternative to running a full MLflow server at beta scale).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f7b3d2e1a456"
down_revision: Union[str, Sequence[str], None] = "e6a2b4c8d901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade: add training_runs table + rolled_back_at column."""
    with op.batch_alter_table("ml_models") as batch_op:
        batch_op.add_column(
            sa.Column("rolled_back_at", sa.DateTime(), nullable=True)
        )

    op.create_table(
        "ml_training_runs",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("model_type", sa.String(length=40), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("params_json", sa.Text(), nullable=True),
        sa.Column("metrics_json", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("model_version", sa.String(length=40), nullable=True),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index(
        op.f("ix_ml_training_runs_model_type"),
        "ml_training_runs",
        ["model_type"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade: drop training_runs table + rolled_back_at column."""
    op.drop_index(op.f("ix_ml_training_runs_model_type"), table_name="ml_training_runs")
    op.drop_table("ml_training_runs")
    with op.batch_alter_table("ml_models") as batch_op:
        batch_op.drop_column("rolled_back_at")
