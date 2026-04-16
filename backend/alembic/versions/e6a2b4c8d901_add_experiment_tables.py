"""Add experiment tables for Phase 9 L5 APTE n-of-1

Revision ID: e6a2b4c8d901
Revises: d5f1c3a2b789
Create Date: 2026-04-16 (Signal Engine Phase 9A Commit 1)

Two new tables for user-initiated personal experiments:

- ``ml_experiments`` -- experiment lifecycle: hypothesis, design (AB/ABAB),
  phase dates, status progression, compliance tracking.
- ``ml_n_of_1_results`` -- APTE estimates with CI, p-value, effect size,
  and compliance counts for completed experiments.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e6a2b4c8d901"
down_revision: Union[str, Sequence[str], None] = "d5f1c3a2b789"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade: create experiment tables."""
    op.create_table(
        "ml_experiments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("experiment_name", sa.String(length=200), nullable=False),
        sa.Column("hypothesis", sa.Text(), nullable=True),
        sa.Column("treatment_metric", sa.String(length=100), nullable=False),
        sa.Column("outcome_metric", sa.String(length=100), nullable=False),
        sa.Column("design", sa.String(length=20), nullable=False),
        sa.Column("baseline_days", sa.Integer(), nullable=False),
        sa.Column("treatment_days", sa.Integer(), nullable=False),
        sa.Column("washout_days", sa.Integer(), nullable=False),
        sa.Column("min_compliance", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("baseline_end", sa.String(length=10), nullable=False),
        sa.Column("treatment_start", sa.String(length=10), nullable=False),
        sa.Column("treatment_end", sa.String(length=10), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("compliant_days_baseline", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("compliant_days_treatment", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ml_experiments_user_id"),
        "ml_experiments",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "ml_n_of_1_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("experiment_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("treatment_metric", sa.String(length=100), nullable=False),
        sa.Column("outcome_metric", sa.String(length=100), nullable=False),
        sa.Column("apte", sa.Float(), nullable=True),
        sa.Column("ci_lower", sa.Float(), nullable=True),
        sa.Column("ci_upper", sa.Float(), nullable=True),
        sa.Column("p_value", sa.Float(), nullable=True),
        sa.Column("effect_size_d", sa.Float(), nullable=True),
        sa.Column("baseline_mean", sa.Float(), nullable=True),
        sa.Column("treatment_mean", sa.Float(), nullable=True),
        sa.Column("baseline_n", sa.Integer(), nullable=False),
        sa.Column("treatment_n", sa.Integer(), nullable=False),
        sa.Column("compliant_days_baseline", sa.Integer(), nullable=False),
        sa.Column("compliant_days_treatment", sa.Integer(), nullable=False),
        sa.Column("method", sa.String(length=40), nullable=False),
        sa.Column("model_version", sa.String(length=40), nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["experiment_id"], ["ml_experiments.id"]),
    )
    op.create_index(
        op.f("ix_ml_n_of_1_results_user_id"),
        "ml_n_of_1_results",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade: drop experiment tables."""
    op.drop_index(op.f("ix_ml_n_of_1_results_user_id"), table_name="ml_n_of_1_results")
    op.drop_table("ml_n_of_1_results")
    op.drop_index(op.f("ix_ml_experiments_user_id"), table_name="ml_experiments")
    op.drop_table("ml_experiments")
