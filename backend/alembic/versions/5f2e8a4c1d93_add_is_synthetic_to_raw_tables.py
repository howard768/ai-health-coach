"""Add is_synthetic column to raw tables for Phase 4.5 synth factory.

Revision ID: 5f2e8a4c1d93
Revises: 1578831d1826
Create Date: 2026-04-14 (Signal Engine Phase 4.5, Commit 3)

Adds a ``is_synthetic`` boolean column (default False, indexed) to each raw
ingestion table that the synth factory will write to:

    sleep_records
    health_metric_records
    activity_records
    meal_records
    food_item_records

Design rationale: option 1 in the Phase 4.5 prep doc. Fails safely because
production aggregates that forget the ``WHERE is_synthetic = false`` filter
still return only real data (synth is absent by column-default construction).
The index supports efficient filtering at scale since almost all production
rows will have ``is_synthetic = False``.

Server default kept in place after the migration so that direct SQL INSERTs
(e.g. Alembic seeds, hand-rolled maintenance scripts) do not need to know
about the synth flag. Python-side model defaults cover the ORM path.

Hand-trimmed to just the new columns plus their indexes. Autogenerate noise
(spurious FK drops on existing tables, EncryptedString type coercions on
oura_tokens / peloton_tokens / garmin_tokens) deliberately excluded, matching
the pattern used in 1578831d1826.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "5f2e8a4c1d93"
down_revision: Union[str, Sequence[str], None] = "1578831d1826"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABLES: tuple[str, ...] = (
    "sleep_records",
    "health_metric_records",
    "activity_records",
    "meal_records",
    "food_item_records",
)


def upgrade() -> None:
    """Add is_synthetic (Boolean, default False, indexed) to each raw table."""
    for table in _TABLES:
        op.add_column(
            table,
            sa.Column(
                "is_synthetic",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
        op.create_index(
            op.f(f"ix_{table}_is_synthetic"),
            table,
            ["is_synthetic"],
        )


def downgrade() -> None:
    """Reverse of upgrade, in reverse order (indexes first, then columns)."""
    for table in reversed(_TABLES):
        op.drop_index(op.f(f"ix_{table}_is_synthetic"), table_name=table)
        op.drop_column(table, "is_synthetic")
