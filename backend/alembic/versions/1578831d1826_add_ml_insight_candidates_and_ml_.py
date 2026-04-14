"""Add ml_insight_candidates and ml_rankings tables

Revision ID: 1578831d1826
Revises: 490671839de6
Create Date: 2026-04-14 (Signal Engine Phase 4)

Phase 4 schema for insight candidates + daily ranked slate. Candidates are
normalized surfaceable findings; rankings are the ranker's per-(user, date)
output. ``was_shown`` + ``feedback`` fields close the user feedback loop.

Hand-trimmed to just the new tables — autogenerate flagged the usual SQLite
foreign-key / EncryptedString noise that is not this migration's concern.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "1578831d1826"
down_revision: Union[str, Sequence[str], None] = "490671839de6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade: ml_insight_candidates + ml_rankings."""
    op.create_table(
        "ml_insight_candidates",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("subject_metrics_json", sa.Text(), nullable=False),
        sa.Column("effect_size", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("novelty", sa.Float(), nullable=False),
        sa.Column("recency_days", sa.Integer(), nullable=False),
        sa.Column("actionability_score", sa.Float(), nullable=False),
        sa.Column("literature_support", sa.Boolean(), nullable=False),
        sa.Column("directional_support", sa.Boolean(), nullable=False),
        sa.Column("causal_support", sa.Boolean(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ml_insight_candidates_kind"), "ml_insight_candidates", ["kind"]
    )
    op.create_index(
        op.f("ix_ml_insight_candidates_user_id"), "ml_insight_candidates", ["user_id"]
    )

    op.create_table(
        "ml_rankings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("surface_date", sa.String(length=10), nullable=False),
        sa.Column("candidate_id", sa.String(length=64), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("ranker_version", sa.String(length=40), nullable=False),
        sa.Column("was_shown", sa.Boolean(), nullable=False),
        sa.Column("shown_at", sa.DateTime(), nullable=True),
        sa.Column("feedback", sa.String(length=20), nullable=True),
        sa.Column("feedback_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "surface_date",
            "rank",
            "ranker_version",
            name="uq_ml_rankings_user_date_rank_version",
        ),
    )
    op.create_index(op.f("ix_ml_rankings_candidate_id"), "ml_rankings", ["candidate_id"])
    op.create_index(op.f("ix_ml_rankings_surface_date"), "ml_rankings", ["surface_date"])
    op.create_index(op.f("ix_ml_rankings_user_id"), "ml_rankings", ["user_id"])


def downgrade() -> None:
    """Downgrade: drop both tables."""
    op.drop_index(op.f("ix_ml_rankings_user_id"), table_name="ml_rankings")
    op.drop_index(op.f("ix_ml_rankings_surface_date"), table_name="ml_rankings")
    op.drop_index(op.f("ix_ml_rankings_candidate_id"), table_name="ml_rankings")
    op.drop_table("ml_rankings")

    op.drop_index(op.f("ix_ml_insight_candidates_user_id"), table_name="ml_insight_candidates")
    op.drop_index(op.f("ix_ml_insight_candidates_kind"), table_name="ml_insight_candidates")
    op.drop_table("ml_insight_candidates")
