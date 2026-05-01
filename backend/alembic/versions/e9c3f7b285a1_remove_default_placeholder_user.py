"""Remove the 'default' placeholder user (MEL-45 part 4).

The 'default' apple_user_id row was inserted in c0518b5194eb to backfill
pre-Sign-in-with-Apple tenant rows so the new FK constraints would attach.
After SIWA shipped (and after the 2026-04-29 reset cleared all production
data), the placeholder is no longer load-bearing:

  - Production has only Apple-signed-in users (or none yet).
  - The pre-MEL-45 single-user backend treated 'default' as a stand-in for
    the operator; multi-user routing (parts 1-3) routes by real
    apple_user_id and oura_user_id instead.
  - claim_default_user.py was the manual reassignment tool. With the
    placeholder gone, the script has no purpose and is dropped in this PR.

The DELETE is wrapped in NOT EXISTS to stay idempotent. FK constraints from
tenant tables to users.apple_user_id are ON DELETE CASCADE, so any orphaned
rows still tagged with user_id='default' (none expected post-2026-04-29) are
removed in the same transaction. The downgrade re-inserts the placeholder
row so older code paths can still find it.

Revision ID: e9c3f7b285a1
Revises: d8e4c1a72b39
Create Date: 2026-04-30
"""
from datetime import datetime
from typing import Sequence, Union

from alembic import op


revision: str = "e9c3f7b285a1"
down_revision: Union[str, Sequence[str], None] = "d8e4c1a72b39"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # CASCADE-deletes any tenant rows still tagged with user_id='default'.
    # Idempotent: no-op if the row already cleared.
    op.execute("DELETE FROM users WHERE apple_user_id = 'default'")


def downgrade() -> None:
    # Re-insert the placeholder so callers that still reference 'default'
    # (rolled-back code) keep working. NOT EXISTS guards against double-insert.
    now = datetime.utcnow().isoformat(sep=" ", timespec="seconds")
    op.execute(
        f"""
        INSERT INTO users (apple_user_id, is_active, is_private_email, created_at, updated_at)
        SELECT 'default', true, false, '{now}', '{now}'
        WHERE NOT EXISTS (SELECT 1 FROM users WHERE apple_user_id = 'default')
        """
    )
