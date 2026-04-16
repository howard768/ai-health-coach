"""Add cohort tables for Phase 8 cross-user clustering

Revision ID: d5f1c3a2b789
Revises: c4e8a2f1b357
Create Date: 2026-04-16 (Signal Engine Phase 8A Commit 1)

Three new tables for opt-in cross-user archetype clustering:

- ``ml_cohort_consent`` -- per-user opt-in status and deletion lifecycle.
- ``ml_anonymized_vectors`` -- pseudonymized, DP-noised pattern vectors
  for clustering. Never contains raw user_ids or raw health data.
- ``ml_cohorts`` -- cluster metadata (label, size, centroid, archetype name).
  One set of rows per monthly clustering run; previous run deactivated.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d5f1c3a2b789"
down_revision: Union[str, Sequence[str], None] = "c4e8a2f1b357"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade: create cohort tables."""
    op.create_table(
        "ml_cohort_consent",
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("opted_in", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("opted_in_at", sa.DateTime(), nullable=True),
        sa.Column("opted_out_at", sa.DateTime(), nullable=True),
        sa.Column("deletion_requested_at", sa.DateTime(), nullable=True),
        sa.Column("deletion_completed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.create_table(
        "ml_anonymized_vectors",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pseudonym_id", sa.String(length=64), nullable=False),
        sa.Column("user_id_encrypted", sa.String(length=255), nullable=False),
        sa.Column("vector_json", sa.Text(), nullable=False),
        sa.Column("feature_names_json", sa.Text(), nullable=False),
        sa.Column("dp_epsilon", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ml_anonymized_vectors_pseudonym_id"),
        "ml_anonymized_vectors",
        ["pseudonym_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_ml_anonymized_vectors_user_id_encrypted"),
        "ml_anonymized_vectors",
        ["user_id_encrypted"],
        unique=False,
    )

    op.create_table(
        "ml_cohorts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cluster_label", sa.Integer(), nullable=False),
        sa.Column("n_members", sa.Integer(), nullable=False),
        sa.Column("centroid_json", sa.Text(), nullable=False),
        sa.Column("archetype_name", sa.String(length=100), nullable=True),
        sa.Column("archetype_description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ml_cohorts_run_id"),
        "ml_cohorts",
        ["run_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade: drop cohort tables."""
    op.drop_index(op.f("ix_ml_cohorts_run_id"), table_name="ml_cohorts")
    op.drop_table("ml_cohorts")
    op.drop_index(
        op.f("ix_ml_anonymized_vectors_user_id_encrypted"),
        table_name="ml_anonymized_vectors",
    )
    op.drop_index(
        op.f("ix_ml_anonymized_vectors_pseudonym_id"),
        table_name="ml_anonymized_vectors",
    )
    op.drop_table("ml_anonymized_vectors")
    op.drop_table("ml_cohort_consent")
