"""Symmetric encryption for OAuth tokens and other secrets at rest.

Fernet (AES-128-CBC + HMAC-SHA256) from the `cryptography` library: authenticated
encryption that prevents both tampering and snooping. Wrapped in ``MultiFernet``
so keys can be rotated without a single big migration window.

Threat model:
- If someone steals the SQLite file or a Postgres backup, OAuth tokens and
  other encrypted columns are ciphertext, not usable credentials.
- Decryption keys live in Railway env vars, never in the DB or codebase.
- A single compromise (env leak plus DB leak) defeats this. Defense in depth,
  not perfect security.

Config:
    ENCRYPTION_KEY      Comma-separated list of Fernet keys. The FIRST key is
                        the active key used for every new write. Remaining
                        keys are tried on decrypt so ciphertext written with a
                        retired key still reads while we drain the DB.
                        Generate one with:
                            python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Behavior by environment:
    APP_ENV=production  Missing or invalid ENCRYPTION_KEY raises
                        EncryptionConfigError on first use (fail closed).
                        Plaintext PHI is never written.
    otherwise (dev, ci) Missing key logs a warning once and falls through
                        unencrypted. Keeps local dev and CI green without
                        needing secrets in the environment.

Legacy plaintext rows: a row whose ciphertext cannot be decoded by any
configured key is assumed to be a pre-encryption row and returned unchanged.
That read is logged at warning level so "legacy row" can be distinguished
from "wrong key" or "tampering" in Sentry.

SQLAlchemy integration: ``EncryptedString`` is a TypeDecorator that encrypts
on write and decrypts on read transparently:

    access_token: Mapped[str] = mapped_column(EncryptedString(2000))
"""

from __future__ import annotations

import logging
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from sqlalchemy.types import String, TypeDecorator

from app.config import settings

logger = logging.getLogger("meld.encryption")


class EncryptionConfigError(RuntimeError):
    """Raised in production when ENCRYPTION_KEY is missing or unparseable."""


_cipher: Optional[MultiFernet] = None
_missing_key_warned: bool = False


def _is_production() -> bool:
    return (settings.app_env or "").strip().lower() == "production"


def _parse_keys(raw: str) -> list[Fernet]:
    """Split a comma-separated key string into Fernet instances.

    Whitespace around each entry is stripped and empty entries are skipped so
    a trailing comma will not explode. Each entry is validated by the Fernet
    constructor, which raises ValueError if the key is not a 32-byte url-safe
    base64 value.
    """
    keys: list[Fernet] = []
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        keys.append(Fernet(entry.encode()))
    return keys


def _get_cipher() -> Optional[MultiFernet]:
    """Return the active cipher, or None when unconfigured in non-prod.

    In production, missing or invalid config raises EncryptionConfigError.
    """
    global _cipher, _missing_key_warned
    if _cipher is not None:
        return _cipher

    raw = settings.encryption_key or ""
    prod = _is_production()

    if not raw:
        if prod:
            raise EncryptionConfigError(
                "ENCRYPTION_KEY is not set but APP_ENV=production. "
                "Refusing to store secrets in plaintext."
            )
        if not _missing_key_warned:
            logger.warning(
                "ENCRYPTION_KEY not set (APP_ENV=%s). Values will be stored "
                "in plaintext. Set ENCRYPTION_KEY before shipping to prod.",
                settings.app_env,
            )
            _missing_key_warned = True
        return None

    try:
        keys = _parse_keys(raw)
    except (ValueError, TypeError) as e:
        if prod:
            raise EncryptionConfigError(f"ENCRYPTION_KEY failed to parse: {e}") from e
        logger.error(
            "ENCRYPTION_KEY invalid, falling back to plaintext in non-prod: %s",
            e,
        )
        return None

    if not keys:
        if prod:
            raise EncryptionConfigError(
                "ENCRYPTION_KEY parsed to zero keys but APP_ENV=production."
            )
        logger.warning("ENCRYPTION_KEY parsed to zero keys.")
        return None

    _cipher = MultiFernet(keys)
    if len(keys) > 1:
        logger.info("Encryption initialized with %d keys (rotation mode).", len(keys))
    return _cipher


def verify_encryption_configured() -> None:
    """Fail fast at app startup if production is missing a usable key.

    Safe to call from non-prod: becomes a no-op that just logs the warning.
    Call from ``app.main`` startup to surface misconfiguration on boot
    instead of on the first PHI write.
    """
    _get_cipher()


def _reset_for_tests() -> None:
    """Drop the cached cipher so tests can manipulate settings and re-init.

    Not part of the public API; imported only by the encryption test module.
    """
    global _cipher, _missing_key_warned
    _cipher = None
    _missing_key_warned = False


def encrypt(plaintext: str | None) -> str | None:
    """Encrypt a string with the active key. Returns None for None input."""
    if plaintext is None:
        return None
    cipher = _get_cipher()
    if cipher is None:
        return plaintext  # dev or ci only; prod would have raised above
    return cipher.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str | None) -> str | None:
    """Decrypt a string. Returns None for None input.

    Tries every configured key. If none match, the input is returned
    unchanged on the assumption it is a pre-encryption legacy row, and the
    miss is logged so legacy rows can be distinguished from rotated-away
    keys or tampering in aggregate metrics.
    """
    if ciphertext is None:
        return None
    cipher = _get_cipher()
    if cipher is None:
        return ciphertext
    try:
        return cipher.decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        logger.warning(
            "encryption.decrypt_miss len=%d prefix=%r",
            len(ciphertext),
            ciphertext[:6],
        )
        return ciphertext
    except (ValueError, UnicodeDecodeError) as e:
        logger.error("encryption.decrypt_error: %s", e)
        return ciphertext


class EncryptedString(TypeDecorator):
    """SQLAlchemy column type that encrypts and decrypts transparently.

    Usage:
        access_token: Mapped[str] = mapped_column(EncryptedString(2000))
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return encrypt(value)

    def process_result_value(self, value, dialect):
        return decrypt(value)
