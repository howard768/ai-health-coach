"""Symmetric encryption for OAuth tokens and other secrets at rest.

Uses Fernet (AES-128-CBC + HMAC) from the `cryptography` library — battle-tested,
authenticated encryption that prevents both tampering and snooping.

Threat model:
- If someone steals the SQLite file or a Postgres backup, OAuth tokens are
  ciphertext, not usable credentials.
- The decryption key (`ENCRYPTION_KEY`) lives in Railway env vars, NEVER in
  the DB or codebase.
- A single compromise (env var leak + DB leak) defeats this. Defense in depth,
  not perfect security.

SQLAlchemy integration: `EncryptedString` is a TypeDecorator that transparently
encrypts on write and decrypts on read. Existing model fields just change type:
    access_token: Mapped[str] = mapped_column(EncryptedString)

Backward compatibility: if a value in the DB is NOT a Fernet token (i.e. it
was stored before encryption was added), `decrypt` returns the raw value
unchanged. This lets us roll out encryption without a data migration — new
writes are encrypted, old reads still work, and the next refresh of any token
will encrypt it.
"""

from __future__ import annotations

import logging
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.types import String, TypeDecorator

from app.config import settings

logger = logging.getLogger("meld.encryption")

_cipher: Optional[Fernet] = None


def _get_cipher() -> Optional[Fernet]:
    """Lazy-load the Fernet cipher. Returns None if no key is configured."""
    global _cipher
    if _cipher is not None:
        return _cipher
    if not settings.encryption_key:
        logger.warning(
            "ENCRYPTION_KEY not set — OAuth tokens will be stored in plaintext. "
            "Set it in Railway env vars before going to production."
        )
        return None
    try:
        _cipher = Fernet(settings.encryption_key.encode())
        return _cipher
    except Exception as e:
        logger.error("Failed to initialize Fernet cipher: %s", e)
        return None


def encrypt(plaintext: str | None) -> str | None:
    """Encrypt a string. Returns None for None input."""
    if plaintext is None:
        return None
    cipher = _get_cipher()
    if cipher is None:
        return plaintext  # Fall through unencrypted in dev — logged as warning
    return cipher.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str | None) -> str | None:
    """Decrypt a string. Returns None for None input.

    If the input is NOT a valid Fernet token, returns it unchanged. This
    handles legacy plaintext rows from before encryption was enabled.
    """
    if ciphertext is None:
        return None
    cipher = _get_cipher()
    if cipher is None:
        return ciphertext
    try:
        return cipher.decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        # Legacy plaintext row — return as-is. Will be encrypted on next write.
        return ciphertext
    except Exception as e:
        logger.error("Decryption failed: %s", e)
        return ciphertext


class EncryptedString(TypeDecorator):
    """SQLAlchemy column type that encrypts/decrypts transparently.

    Usage:
        access_token: Mapped[str] = mapped_column(EncryptedString)
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return encrypt(value)

    def process_result_value(self, value, dialect):
        return decrypt(value)
