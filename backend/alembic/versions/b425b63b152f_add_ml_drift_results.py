"""Add ml_drift_results table for per-feature KS drift snapshots.

Revision ID: b425b63b152f
Revises: 80b80e94d52c
Create Date: 2026-04-17 (drift-stats table, feature-drift endpoint follow-up)

One row per ``(synth_run_id, feature_key)`` produced by ``synth_drift_job``.
Unblocks ``/ops/ml/feature-drift``, which currently returns empty arrays
because no drift-stats table exists. The endpoint queries this table for
the most recent batch (MAX(computed_at)) and surfaces it as
``features_over_threshold``.

Non-destructive: net-new table with composite + per-column indexes.
Downgrade drops the table outright.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b425b63b152f"
down_revision: Union[str, Sequence[str], None] = "80b80e94d52c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade: ml_drift_results."""
    op.create_table(
        "ml_drift_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("synth_run_id", sa.String(length=36), nullable=False),
        sa.Column("feature_key", sa.String(length=120), nullable=False),
        sa.Column("ks_statistic", sa.Float(), nullable=False),
        sa.Column("ks_pvalue", sa.Float(), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("drifted", sa.Boolean(), nullable=False),
        sa.Column("sample_size_real", sa.Integer(), nullable=False),
        sa.Column("sample_size_synth", sa.Integer(), nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ml_drift_results_synth_run_id",
        "ml_drift_results",
        ["synth_run_id"],
    )
    op.create_index(
        "ix_ml_drift_results_feature_key",
        "ml_drift_results",
        ["feature_key"],
    )
    op.create_index(
        "ix_ml_drift_results_computed_at",
        "ml_drift_results",
        ["computed_at"],
    )
    op.create_index(
        "ix_ml_drift_results_run_feature",
        "ml_drift_results",
        ["synth_run_id", "feature_key"],
    )


def downgrade() -> None:
    """Downgrade: drop ml_drift_results."""
    op.drop_index("ix_ml_drift_results_run_feature", table_name="ml_drift_results")
    op.drop_index("ix_ml_drift_results_computed_at", table_name="ml_drift_results")
    op.drop_index("ix_ml_drift_results_feature_key", table_name="ml_drift_results")
    op.drop_index("ix_ml_drift_results_synth_run_id", table_name="ml_drift_results")
    op.drop_table("ml_drift_results")
