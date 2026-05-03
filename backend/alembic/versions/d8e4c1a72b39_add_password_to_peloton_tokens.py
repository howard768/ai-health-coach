"""add encrypted password to peloton_tokens

Revision ID: d8e4c1a72b39
Revises: b5c8f3e29a04
Create Date: 2026-04-30 22:30:00.000000

Adds an encrypted `password` column to `peloton_tokens` so the Peloton
sync flow can re-authenticate via pylotoncycle on each sync cycle.

Pre-PR-MEL-44 the Peloton sync was structurally broken (see [MEL-44]
plan + PR #89): `pylotoncycle.PylotonCycle` authenticates via
username + password and does NOT expose a session token suitable for
persistence. `PelotonToken.session_id` stored a literal "oauth"
placeholder, not a real session. The pre-PR-#89 call site
`PelotonClient(session_id=..., user_id=...)` raised TypeError on every
scheduled sync. PR #89 short-circuited that with a clean
`needs_reauth` status; this migration is the substrate for the proper
fix.

Scope of this PR: ONLY the migration + model field. Brock reviews the
Tier 3 PHI-table migration in isolation. The sync rewire (Tier 0 once
column lives in main) lands in a follow-up PR:
  - Connect flow captures username + password
  - sync_user_data calls `PelotonClient.login(username, password)` on
    every sync (no session caching needed; pylotoncycle handles its
    internal token state per-process)
  - Drop the legacy `_sync_user_data_legacy` and `session_id`
    placeholder usage; mark `session_id` column for removal in a
    later cleanup migration

Migration safety:
  - Nullable column. Existing rows get NULL. The sync flow stays in
    `needs_reauth` short-circuit until the column is populated AND
    the sync rewire ships. No regression for existing users.
  - `EncryptedString(2000)` uses the project's Fernet AT-REST encryption
    (see app/core/encryption.py). DB breach yields ciphertext, not
    plaintext credentials.
  - Postgres dialect parity per feedback_postgres_dialect_parity.md:
    no boolean defaults, no `sa.text("0/1")` traps. ADD COLUMN with
    `nullable=True` is dialect-neutral.
  - The underlying SQL column type is `TEXT` (or `VARCHAR(2000)` in
    raw SQL terms), `EncryptedString` is a SQLAlchemy TypeDecorator
    around String, not a custom DB type.

Rollback: `op.drop_column`. Non-destructive in the sense that the
encrypted password is regenerable (user re-enters it at next connect).

Trust boundary: storing a plaintext-equivalent (encrypted at rest) is
a real attack surface increase. The alternative (replacing pylotoncycle
with a session-token-aware client) is more work and was rejected for
this iteration. Tracked in MEL-44 plan as path A.

Tier 3: `peloton_*` PHI table is on the hard-refuse list per CLAUDE.md.
Brock's explicit override authorized this work in MEL-44 plan review.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d8e4c1a72b39"
# Linear chain: MEL-45 part 1 (b5c8f3e29a04) merged first to main, so this
# rebases onto it. Linear history avoids the multi-head case we'd otherwise
# need an alembic merge migration to flatten.
down_revision: Union[str, Sequence[str], None] = "b5c8f3e29a04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable so existing rows don't need a backfill, they stay in
    # `needs_reauth` short-circuit until the user reconnects (which
    # captures both username and password under the new flow).
    #
    # Underlying SQL is VARCHAR(2000); EncryptedString is a SQLAlchemy
    # TypeDecorator that ciphers on bind / deciphers on result. The
    # 2000-char cap accommodates Fernet ciphertext expansion (~33%
    # over plaintext + base64 padding) for plausible password lengths.
    op.add_column(
        "peloton_tokens",
        sa.Column("password", sa.String(2000), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("peloton_tokens", "password")
