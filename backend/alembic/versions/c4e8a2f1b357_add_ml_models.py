"""Add ml_models table for model registry

Revision ID: c4e8a2f1b357
Revises: b3d7f1e9a245
Create Date: 2026-04-15 (Signal Engine Phase 7A Commit 1)

One row per trained model. Tracks model type (e.g. "ranker"), version,
file hash (SHA-256 of the CoreML .mlmodel), R2 key, training metadata
(samples, val NDCG, feature names, hyperparams), and active status.

Also adds ``heuristic_score`` column to ``ml_rankings`` for A/B shadow
comparison between heuristic and learned rankers.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4e8a2f1b357"
down_revision: Union[str, Sequence[str], None] = "b3d7f1e9a245"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade: ml_models + heuristic_score column."""
    op.create_table(
        "ml_models",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("model_type", sa.String(length=40), nullable=False),
        sa.Column("model_version", sa.String(length=40), nullable=False),
        sa.Column("file_hash", sa.String(length=64), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("r2_key", sa.String(length=255), nullable=True),
        sa.Column("download_url", sa.String(length=512), nullable=True),
        sa.Column("train_samples", sa.Integer(), nullable=False),
        sa.Column("val_ndcg", sa.Float(), nullable=True),
        sa.Column("feature_names_json", sa.Text(), nullable=False),
        sa.Column("hyperparams_json", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("model_type", "model_version", name="uq_ml_models_type_version"),
    )
    op.create_index(
        op.f("ix_ml_models_model_type"),
        "ml_models",
        ["model_type"],
        unique=False,
    )

    # A/B shadow: store heuristic score alongside learned score.
    with op.batch_alter_table("ml_rankings") as batch_op:
        batch_op.add_column(
            sa.Column(
                "heuristic_score",
                sa.Float(),
                nullable=True,
            )
        )


def downgrade() -> None:
    """Downgrade: drop ml_models + heuristic_score column."""
    with op.batch_alter_table("ml_rankings") as batch_op:
        batch_op.drop_column("heuristic_score")
    op.drop_index(op.f("ix_ml_models_model_type"), table_name="ml_models")
    op.drop_table("ml_models")
