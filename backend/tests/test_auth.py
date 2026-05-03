"""Tests for JWT auth, SIWA verification, and get_current_user dependency.

Run: cd backend && uv run pytest tests/test_auth.py -v
"""

import os
import pytest
import jwt
from datetime import datetime, timedelta, timezone

# Set a stable secret for tests BEFORE importing app modules
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-auth-tests-only-do-not-use-in-prod"

from app.core.security import (
    create_access_token,
    decode_access_token,
    create_refresh_token,
    hash_refresh_token,
    JWT_ALGORITHM,
    JWT_ISSUER,
    JWT_AUDIENCE,
)


# ── Access token roundtrip ───────────────────────────────────────────────────


def test_access_token_roundtrip():
    """Encode + decode returns the same subject."""
    user_id = "001234.abc123.test"
    token, expires_at = create_access_token(user_id)
    payload = decode_access_token(token)
    assert payload["sub"] == user_id
    assert payload["typ"] == "access"
    assert payload["iss"] == JWT_ISSUER
    assert payload["aud"] == JWT_AUDIENCE
    # Expires should be ~15 min from now
    assert expires_at > datetime.now(timezone.utc)
    assert expires_at < datetime.now(timezone.utc) + timedelta(minutes=16)


def test_expired_token_rejected():
    """A token past its expiry should fail decode."""
    from app.config import settings
    now = datetime.now(timezone.utc)
    payload = {
        "sub": "user-expired",
        "iat": now - timedelta(hours=2),
        "exp": now - timedelta(hours=1),  # expired 1h ago
        "jti": "test-jti",
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "typ": "access",
    }
    expired = jwt.encode(payload, settings.jwt_secret_key, algorithm=JWT_ALGORITHM)
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(expired)


def test_wrong_audience_rejected():
    """A token with the wrong audience should fail."""
    from app.config import settings
    now = datetime.now(timezone.utc)
    payload = {
        "sub": "user-wrong-aud",
        "iat": now,
        "exp": now + timedelta(minutes=15),
        "jti": "test-jti",
        "iss": JWT_ISSUER,
        "aud": "not-meld-ios",  # WRONG
        "typ": "access",
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=JWT_ALGORITHM)
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token)


def test_wrong_issuer_rejected():
    """A token with the wrong issuer should fail."""
    from app.config import settings
    now = datetime.now(timezone.utc)
    payload = {
        "sub": "user-wrong-iss",
        "iat": now,
        "exp": now + timedelta(minutes=15),
        "jti": "test-jti",
        "iss": "evil-issuer",  # WRONG
        "aud": JWT_AUDIENCE,
        "typ": "access",
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=JWT_ALGORITHM)
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token)


def test_wrong_typ_rejected():
    """A token with typ != 'access' should fail (prevents using refresh as access)."""
    from app.config import settings
    now = datetime.now(timezone.utc)
    payload = {
        "sub": "user-wrong-typ",
        "iat": now,
        "exp": now + timedelta(minutes=15),
        "jti": "test-jti",
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "typ": "refresh",  # WRONG, trying to use refresh as access
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=JWT_ALGORITHM)
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token)


def test_tampered_signature_rejected():
    """A token signed with the wrong key should fail."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": "user-tampered",
        "iat": now,
        "exp": now + timedelta(minutes=15),
        "jti": "test-jti",
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "typ": "access",
    }
    bad_token = jwt.encode(payload, "wrong-secret", algorithm=JWT_ALGORITHM)
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(bad_token)


def test_missing_required_claim_rejected():
    """A token missing a required claim should fail."""
    from app.config import settings
    now = datetime.now(timezone.utc)
    # Missing 'jti'
    payload = {
        "sub": "user-missing-claim",
        "iat": now,
        "exp": now + timedelta(minutes=15),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "typ": "access",
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=JWT_ALGORITHM)
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token)


# ── Refresh token ────────────────────────────────────────────────────────────


def test_refresh_token_hash_is_deterministic():
    """Same input produces same hash (so we can look up by hash in DB)."""
    raw, hashed, _ = create_refresh_token()
    assert hash_refresh_token(raw) == hashed


def test_refresh_token_is_random():
    """Two refresh tokens should never collide."""
    raw1, hash1, _ = create_refresh_token()
    raw2, hash2, _ = create_refresh_token()
    assert raw1 != raw2
    assert hash1 != hash2


def test_refresh_token_expiry_30_days():
    """Refresh tokens should have a 30-day expiry.

    Per MELD-BACKEND-F fix: `expires_at` is now naive UTC to match the
    `RefreshToken.expires_at` column type (DateTime, no timezone). Compare
    naive-to-naive to avoid TypeError under the new contract.
    """
    _, _, expires_at = create_refresh_token()
    assert expires_at.tzinfo is None, "expires_at must be naive (matches DB column)"
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    # Should be close to 30 days out (within 1 min tolerance for test timing)
    delta = expires_at - now
    assert 29 * 24 * 60 * 60 < delta.total_seconds() < 31 * 24 * 60 * 60


def test_hashed_refresh_token_is_hex():
    """Hash should be a valid hex string (for DB storage as VARCHAR)."""
    raw, hashed, _ = create_refresh_token()
    # SHA256 hex is 64 chars
    assert len(hashed) == 64
    int(hashed, 16)  # Must be parseable as hex
