"""Add L3 Granger + L4 DoWhy tables and directional/causal columns

Revision ID: b3d7f1e9a245
Revises: a7c9f2b5e483
Create Date: 2026-04-15 (Signal Engine Phase 6 Commit 1)

Adds ``directional_support`` and ``causal_support`` boolean columns to the
existing ``user_correlations`` table. L3 Granger sets ``directional_support``
when a pair passes the Granger F-test (p < 0.05). L4 DoWhy sets
``causal_support`` when ATE CI excludes zero AND all 3 refutation tests pass.

Creates two new tables:

- ``ml_directional_tests`` -- one row per Granger test attempt (pass or fail).
  Stores ADF stationarity, differencing order, F-stat, p-value, optimal lag.
- ``ml_causal_estimates`` -- one row per DoWhy estimation attempt. Stores
  ATE, confidence interval, and the pass/fail of each of the three DoWhy
  refutation tests (placebo treatment, random common cause, subset).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b3d7f1e9a245"
down_revision: Union[str, Sequence[str], None] = "a7c9f2b5e483"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade: add L3/L4 columns + tables."""
    # -- Columns on existing user_correlations ---------------------------------
    with op.batch_alter_table("user_correlations") as batch_op:
        batch_op.add_column(
            sa.Column(
                "directional_support",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )
        batch_op.add_column(
            sa.Column(
                "causal_support",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )

    # -- ml_directional_tests --------------------------------------------------
    op.create_table(
        "ml_directional_tests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("source_metric", sa.String(length=100), nullable=False),
        sa.Column("target_metric", sa.String(length=100), nullable=False),
        sa.Column("lag_days", sa.Integer(), nullable=False),
        sa.Column("is_stationary", sa.Boolean(), nullable=False),
        sa.Column("differencing_order", sa.Integer(), nullable=False),
        sa.Column("f_statistic", sa.Float(), nullable=True),
        sa.Column("p_value", sa.Float(), nullable=True),
        sa.Column("max_lag_tested", sa.Integer(), nullable=False),
        sa.Column("optimal_lag", sa.Integer(), nullable=True),
        sa.Column("significant", sa.Boolean(), nullable=False),
        sa.Column("model_version", sa.String(length=40), nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ml_directional_tests_user_id"),
        "ml_directional_tests",
        ["user_id"],
        unique=False,
    )

    # -- ml_causal_estimates ---------------------------------------------------
    op.create_table(
        "ml_causal_estimates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("treatment_metric", sa.String(length=100), nullable=False),
        sa.Column("outcome_metric", sa.String(length=100), nullable=False),
        sa.Column("lag_days", sa.Integer(), nullable=False),
        sa.Column("estimator", sa.String(length=40), nullable=False),
        sa.Column("ate", sa.Float(), nullable=True),
        sa.Column("ate_ci_lower", sa.Float(), nullable=True),
        sa.Column("ate_ci_upper", sa.Float(), nullable=True),
        sa.Column("ate_p_value", sa.Float(), nullable=True),
        sa.Column("placebo_treatment_passed", sa.Boolean(), nullable=False),
        sa.Column("random_common_cause_passed", sa.Boolean(), nullable=False),
        sa.Column("subset_passed", sa.Boolean(), nullable=False),
        sa.Column("all_refutations_passed", sa.Boolean(), nullable=False),
        sa.Column("ci_excludes_zero", sa.Boolean(), nullable=False),
        sa.Column("n_samples", sa.Integer(), nullable=False),
        sa.Column("model_version", sa.String(length=40), nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ml_causal_estimates_user_id"),
        "ml_causal_estimates",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade: drop L3/L4 tables + columns."""
    op.drop_index(
        op.f("ix_ml_causal_estimates_user_id"), table_name="ml_causal_estimates"
    )
    op.drop_table("ml_causal_estimates")
    op.drop_index(
        op.f("ix_ml_directional_tests_user_id"), table_name="ml_directional_tests"
    )
    op.drop_table("ml_directional_tests")
    with op.batch_alter_table("user_correlations") as batch_op:
        batch_op.drop_column("causal_support")
        batch_op.drop_column("directional_support")
