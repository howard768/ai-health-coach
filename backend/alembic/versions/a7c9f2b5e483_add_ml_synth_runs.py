"""Add ml_synth_runs table for synth cohort manifest audit

Revision ID: a7c9f2b5e483
Revises: 5f2e8a4c1d93
Create Date: 2026-04-15 (Signal Engine Phase 4.5 Commit 6)

One row per ``ml.api.generate_synth_cohort`` call. Primary key is the
same uuid4 hex emitted on the returned ``CohortManifest.run_id``, so a
scheduler log line referencing a run id can be cross-referenced to
this table and to every ``is_synthetic=True`` row in the raw tables.

Hand-trimmed to just this new table. Autogenerate flagged the usual
SQLite/EncryptedString noise on pre-existing token tables that is not
this migration's concern. Same pattern as ``1578831d1826``.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7c9f2b5e483"
down_revision: Union[str, Sequence[str], None] = "5f2e8a4c1d93"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade: ml_synth_runs."""
    op.create_table(
        "ml_synth_runs",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=True),
        sa.Column("generator", sa.String(length=32), nullable=False),
        sa.Column("n_users", sa.Integer(), nullable=False),
        sa.Column("days", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.String(length=10), nullable=False),
        sa.Column("end_date", sa.String(length=10), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("adversarial_fraction", sa.Float(), nullable=False),
        sa.Column("user_ids_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("run_id"),
    )


def downgrade() -> None:
    """Downgrade: drop ml_synth_runs."""
    op.drop_table("ml_synth_runs")
