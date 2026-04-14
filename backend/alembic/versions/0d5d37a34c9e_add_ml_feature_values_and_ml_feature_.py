"""Add ml_feature_values and ml_feature_catalog tables

Revision ID: 0d5d37a34c9e
Revises: f3d7a9b25e81
Create Date: 2026-04-14 10:46:43.140108

First schema change for the Signal Engine build. Creates the feature store
backing tables. Reads (and writes) happen only from backend/ml/features/.

Autogenerate originally flagged a bunch of unrelated deltas (foreign key
constraints + EncryptedString type changes) because of pre-existing drift
between the SQLite introspection and the SQLAlchemy models. Those are not
this migration's concern, so this file is hand-trimmed to only the two new
tables.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0d5d37a34c9e"
down_revision: Union[str, Sequence[str], None] = "f3d7a9b25e81"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: add ml_feature_catalog + ml_feature_values."""
    op.create_table(
        "ml_feature_catalog",
        sa.Column("feature_key", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("domain", sa.String(length=40), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("unit", sa.String(length=30), nullable=False),
        sa.Column("builder_module", sa.String(length=100), nullable=False),
        sa.Column("current_version", sa.String(length=20), nullable=False),
        sa.Column("requires_features", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("feature_key"),
    )
    op.create_table(
        "ml_feature_values",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("feature_key", sa.String(length=120), nullable=False),
        sa.Column("feature_date", sa.String(length=10), nullable=False),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("is_observed", sa.Boolean(), nullable=False),
        sa.Column("imputed_by", sa.String(length=40), nullable=True),
        sa.Column("source_hash", sa.String(length=64), nullable=True),
        sa.Column("feature_version", sa.String(length=20), nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "feature_key",
            "feature_date",
            "feature_version",
            name="uq_ml_feature_values_user_key_date_version",
        ),
    )
    op.create_index(
        op.f("ix_ml_feature_values_feature_date"),
        "ml_feature_values",
        ["feature_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ml_feature_values_feature_key"),
        "ml_feature_values",
        ["feature_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ml_feature_values_user_id"),
        "ml_feature_values",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema: drop the two ml tables."""
    op.drop_index(op.f("ix_ml_feature_values_user_id"), table_name="ml_feature_values")
    op.drop_index(op.f("ix_ml_feature_values_feature_key"), table_name="ml_feature_values")
    op.drop_index(op.f("ix_ml_feature_values_feature_date"), table_name="ml_feature_values")
    op.drop_table("ml_feature_values")
    op.drop_table("ml_feature_catalog")
