"""Refresh token storage for JWT auth.

Refresh tokens are opaque random strings (not JWTs) stored as SHA256 hashes.
Each issuance creates a new row; rotation links via `replaced_by`. Reuse
detection (presenting a revoked token) should revoke the entire chain for
the user as an anti-theft measure — see `routers/auth_apple.py`.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.core.time import utcnow_naive


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    # Primary key is the SHA256 hex of the raw token. We never store the raw
    # token itself — a DB breach shouldn't hand attackers usable sessions.
    id: Mapped[str] = mapped_column(String(128), primary_key=True)

    # FK to users.apple_user_id (our natural key — see schema doc)
    user_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("users.apple_user_id", ondelete="CASCADE"),
        index=True,
    )

    # iOS identifierForVendor — lets us show "active sessions" later and
    # helps detect impossible-travel patterns (same device, different continent).
    device_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # 30-day expiry from issuance
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    # When the token was revoked (logout, rotation, or chain revocation). NULL = active.
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Rotation chain — points to the hash of the token that replaced this one.
    # If a REVOKED token is presented for refresh, we walk this chain and
    # revoke every descendant (reuse detection).
    replaced_by: Mapped[str | None] = mapped_column(String(128), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)
