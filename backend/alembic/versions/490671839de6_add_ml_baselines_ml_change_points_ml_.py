"""Add ml_baselines, ml_change_points, ml_forecasts, ml_anomalies tables

Revision ID: 490671839de6
Revises: 0d5d37a34c9e
Create Date: 2026-04-14 (Signal Engine Phase 2)

Schema for L1 baselines (STL + BOCPD), forecasting (seasonal-naive + Prophet
ensemble), and residual-anomaly detection. Shadow mode only; nothing reads
these tables yet outside ``backend/ml/``.

Hand-trimmed to just the new tables, autogenerate flagged the usual SQLite
quirks (foreign-key constraints on existing tables, EncryptedString vs
TEXT type drift) that are not this migration's concern.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "490671839de6"
down_revision: Union[str, Sequence[str], None] = "0d5d37a34c9e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade: four new ml_ tables."""
    op.create_table(
        "ml_baselines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("metric_key", sa.String(length=120), nullable=False),
        sa.Column("window_days", sa.Integer(), nullable=False),
        sa.Column("trend_mean", sa.Float(), nullable=True),
        sa.Column("trend_slope", sa.Float(), nullable=True),
        sa.Column("seasonal_amplitude", sa.Float(), nullable=True),
        sa.Column("residual_std", sa.Float(), nullable=True),
        sa.Column("last_observed_date", sa.String(length=10), nullable=False),
        sa.Column("observed_days_in_window", sa.Integer(), nullable=False),
        sa.Column("model_version", sa.String(length=20), nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "metric_key",
            "model_version",
            name="uq_ml_baselines_user_metric_version",
        ),
    )
    op.create_index(op.f("ix_ml_baselines_metric_key"), "ml_baselines", ["metric_key"])
    op.create_index(op.f("ix_ml_baselines_user_id"), "ml_baselines", ["user_id"])

    op.create_table(
        "ml_change_points",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("metric_key", sa.String(length=120), nullable=False),
        sa.Column("change_date", sa.String(length=10), nullable=False),
        sa.Column("detector", sa.String(length=20), nullable=False),
        sa.Column("probability", sa.Float(), nullable=True),
        sa.Column("magnitude", sa.Float(), nullable=True),
        sa.Column("model_version", sa.String(length=20), nullable=False),
        sa.Column("detected_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "metric_key",
            "change_date",
            "detector",
            name="uq_ml_change_points_user_metric_date_detector",
        ),
    )
    op.create_index(op.f("ix_ml_change_points_change_date"), "ml_change_points", ["change_date"])
    op.create_index(op.f("ix_ml_change_points_metric_key"), "ml_change_points", ["metric_key"])
    op.create_index(op.f("ix_ml_change_points_user_id"), "ml_change_points", ["user_id"])

    op.create_table(
        "ml_forecasts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("metric_key", sa.String(length=120), nullable=False),
        sa.Column("target_date", sa.String(length=10), nullable=False),
        sa.Column("made_on", sa.String(length=10), nullable=False),
        sa.Column("y_hat", sa.Float(), nullable=True),
        sa.Column("y_hat_low", sa.Float(), nullable=True),
        sa.Column("y_hat_high", sa.Float(), nullable=True),
        sa.Column("model_version", sa.String(length=40), nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "metric_key",
            "target_date",
            "made_on",
            "model_version",
            name="uq_ml_forecasts_user_metric_target_made_version",
        ),
    )
    op.create_index(op.f("ix_ml_forecasts_metric_key"), "ml_forecasts", ["metric_key"])
    op.create_index(op.f("ix_ml_forecasts_target_date"), "ml_forecasts", ["target_date"])
    op.create_index(op.f("ix_ml_forecasts_user_id"), "ml_forecasts", ["user_id"])

    op.create_table(
        "ml_anomalies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("metric_key", sa.String(length=120), nullable=False),
        sa.Column("observation_date", sa.String(length=10), nullable=False),
        sa.Column("observed_value", sa.Float(), nullable=True),
        sa.Column("forecasted_value", sa.Float(), nullable=True),
        sa.Column("residual", sa.Float(), nullable=False),
        sa.Column("z_score", sa.Float(), nullable=False),
        sa.Column("direction", sa.String(length=4), nullable=False),
        sa.Column("confirmed_by_bocpd", sa.Boolean(), nullable=False),
        sa.Column("model_version", sa.String(length=40), nullable=False),
        sa.Column("detected_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "metric_key",
            "observation_date",
            "model_version",
            name="uq_ml_anomalies_user_metric_date_version",
        ),
    )
    op.create_index(op.f("ix_ml_anomalies_metric_key"), "ml_anomalies", ["metric_key"])
    op.create_index(op.f("ix_ml_anomalies_observation_date"), "ml_anomalies", ["observation_date"])
    op.create_index(op.f("ix_ml_anomalies_user_id"), "ml_anomalies", ["user_id"])


def downgrade() -> None:
    """Downgrade: drop the four ml_ tables."""
    op.drop_index(op.f("ix_ml_anomalies_user_id"), table_name="ml_anomalies")
    op.drop_index(op.f("ix_ml_anomalies_observation_date"), table_name="ml_anomalies")
    op.drop_index(op.f("ix_ml_anomalies_metric_key"), table_name="ml_anomalies")
    op.drop_table("ml_anomalies")

    op.drop_index(op.f("ix_ml_forecasts_user_id"), table_name="ml_forecasts")
    op.drop_index(op.f("ix_ml_forecasts_target_date"), table_name="ml_forecasts")
    op.drop_index(op.f("ix_ml_forecasts_metric_key"), table_name="ml_forecasts")
    op.drop_table("ml_forecasts")

    op.drop_index(op.f("ix_ml_change_points_user_id"), table_name="ml_change_points")
    op.drop_index(op.f("ix_ml_change_points_metric_key"), table_name="ml_change_points")
    op.drop_index(op.f("ix_ml_change_points_change_date"), table_name="ml_change_points")
    op.drop_table("ml_change_points")

    op.drop_index(op.f("ix_ml_baselines_user_id"), table_name="ml_baselines")
    op.drop_index(op.f("ix_ml_baselines_metric_key"), table_name="ml_baselines")
    op.drop_table("ml_baselines")
