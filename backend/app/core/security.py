"""JWT issuance, verification, and refresh-token hashing for Meld backend.

Design decisions (see `ai-health-coach/docs/audit-ultraplan.md`):
- **HS256** for our own tokens — single-backend, single-client system. Auth0's
  guidance is that HS256 is appropriate when all verifiers are within your
  security perimeter. Switch to RS256 if we add a second verifier later.
- **Access tokens**: 15 min expiry, JWT with `sub`, `exp`, `iat`, `jti`, `iss`,
  `aud`, `typ="access"`. Short-lived so revocation is rarely needed.
- **Refresh tokens**: 30 day expiry, opaque random string stored hashed in DB.
  Rotated on every use. Reuse detection revokes the entire chain on replay.
- **Explicit `algorithms=["HS256"]`** on every `jwt.decode` — required by
  RFC 8725 §2.1 to prevent algorithm confusion (CVE-2022-29217).

References:
- RFC 8725 JWT Best Current Practices: https://www.rfc-editor.org/rfc/rfc8725.html
- OWASP JWT Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_for_Java_Cheat_Sheet.html
- Auth0 refresh rotation: https://auth0.com/docs/secure/tokens/refresh-tokens/refresh-token-rotation
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.config import settings

# ── Constants ────────────────────────────────────────────────────────────────

ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 30

# JWT claims — keep these in sync between issue and verify paths.
JWT_ALGORITHM = "HS256"
JWT_ISSUER = "meld-api"
JWT_AUDIENCE = "meld-ios"
JWT_TYPE_ACCESS = "access"


# ── Access Token ─────────────────────────────────────────────────────────────


def create_access_token(user_id: str) -> tuple[str, datetime]:
    """Issue a short-lived HS256 access token for the given user.

    Returns (token, expires_at). The caller decides what to do with the expiry
    (log it, return in response, etc.).
    """
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": expires_at,
        "jti": str(uuid.uuid4()),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "typ": JWT_TYPE_ACCESS,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=JWT_ALGORITHM), expires_at


def decode_access_token(token: str) -> dict:
    """Verify a Meld access token. Raises `jwt.InvalidTokenError` on failure.

    This enforces every security invariant from the RFC 8725 checklist:
    - Explicit algorithm (no `alg=none` confusion)
    - Explicit audience + issuer
    - Required claims enforced
    - Type discriminator checked (so a refresh token can't be used as access)
    """
    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[JWT_ALGORITHM],
        audience=JWT_AUDIENCE,
        issuer=JWT_ISSUER,
        options={"require": ["exp", "iat", "sub", "jti", "typ"]},
    )
    if payload.get("typ") != JWT_TYPE_ACCESS:
        raise jwt.InvalidTokenError("Wrong token type")
    return payload


# ── Refresh Token ────────────────────────────────────────────────────────────


def create_refresh_token() -> tuple[str, str, datetime]:
    """Generate a new opaque refresh token and its DB storage hash.

    Returns:
        (raw_token, hashed_id, expires_at)

    - `raw_token` is what we send to the client (never stored server-side).
    - `hashed_id` is the SHA256 hex of the raw token — used as the primary key
      in `refresh_tokens`. Hashing means a DB breach doesn't yield usable
      tokens.
    - `expires_at` is 30 days out.
    """
    raw = secrets.token_urlsafe(64)
    hashed_id = hash_refresh_token(raw)
    expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    return raw, hashed_id, expires_at


def hash_refresh_token(raw: str) -> str:
    """SHA256-hex of a refresh token. Stored as primary key in `refresh_tokens`."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
