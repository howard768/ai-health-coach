"""TENANT_TABLES FK followup: garmin_daily_records, source_priorities, workout_records

Revision ID: a4e9c2b71f08
Revises: b425b63b152f
Create Date: 2026-04-30 12:50:00

Per audit_2026_04_29/alembic_audit.md (SHOULD-FIX): three tables have a
``user_id`` column but were not in the c0518b5194eb FK loop. Without an
FK to ``users.apple_user_id``, deleting a user via /auth/delete leaves
orphan rows on these tables — both a privacy concern (data leak after
the user thinks they're gone) and a compliance one (GDPR right-to-erasure,
HIPAA dispose-after-purpose).

Tables fixed:

  - garmin_daily_records (per-day Garmin sync; missed when the FK loop
    was first written)
  - source_priorities (per-user metric source preferences)
  - workout_records (per-user workout history)

Tables intentionally NOT fixed:

  - notification_records (outbound push audit log; we want this to
    survive user deletion as forensic record)
  - food_item_records (no user_id column; PR #72 correctly removed it
    from the FK loop)
  - ml_anonymized_vectors / ml_cohort_consent (privacy-stripped or
    user-keyed; separate cleanup)
  - other ml_* tables with user_id (research data; intentionally
    survives user deletion for population-level analysis. Out of scope
    for this PR; a separate one will set up cohort-style anonymization.)
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a4e9c2b71f08"
down_revision: Union[str, Sequence[str], None] = "b425b63b152f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Same shape as TENANT_TABLES in c0518b5194eb. Each entry's ``user_id``
# column gets an FK to ``users.apple_user_id`` with ON DELETE CASCADE.
TENANT_TABLES_FOLLOWUP = [
    "garmin_daily_records",
    "source_priorities",
    "workout_records",
]


def upgrade() -> None:
    """Add user_id FK constraints on tables missed by c0518b5194eb."""
    for tbl in TENANT_TABLES_FOLLOWUP:
        with op.batch_alter_table(tbl) as batch:
            batch.create_foreign_key(
                f"fk_{tbl}_user",
                "users",
                ["user_id"],
                ["apple_user_id"],
                ondelete="CASCADE",
            )


def downgrade() -> None:
    """Drop the FK constraints (table data preserved)."""
    for tbl in TENANT_TABLES_FOLLOWUP:
        with op.batch_alter_table(tbl) as batch:
            batch.drop_constraint(f"fk_{tbl}_user", type_="foreignkey")
