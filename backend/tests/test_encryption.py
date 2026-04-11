"""Tests for the OAuth-token-at-rest encryption layer.

Run: cd backend && uv run python -m pytest tests/test_encryption.py -v
"""

import os

# Use a test key — must be a valid Fernet key (32 url-safe base64 bytes)
os.environ["ENCRYPTION_KEY"] = "T0TXLkHFSeZRYGIIejSFVkhQrvRE-bWLkwXSkkdWiKQ="

# Force settings to re-read by importing after env is set
from app.core.encryption import encrypt, decrypt, _get_cipher


def test_roundtrip():
    plaintext = "fake-oura-access-token-abc123-with-special!@#chars"
    ct = encrypt(plaintext)
    assert ct is not None
    assert ct != plaintext
    assert decrypt(ct) == plaintext


def test_none_passthrough():
    assert encrypt(None) is None
    assert decrypt(None) is None


def test_empty_string_roundtrip():
    ct = encrypt("")
    assert decrypt(ct) == ""


def test_long_token_roundtrip():
    """Garmin garth sessions can be 1000+ chars."""
    long_plaintext = "x" * 5000
    ct = encrypt(long_plaintext)
    assert decrypt(ct) == long_plaintext


def test_legacy_plaintext_passthrough():
    """Reading a legacy non-Fernet value should not crash — return it as-is."""
    legacy = "old-plaintext-token-from-before-encryption"
    assert decrypt(legacy) == legacy


def test_each_encryption_unique():
    """Fernet uses random IVs — same plaintext produces different ciphertexts."""
    plaintext = "same-input"
    ct1 = encrypt(plaintext)
    ct2 = encrypt(plaintext)
    assert ct1 != ct2  # Different IVs
    assert decrypt(ct1) == plaintext
    assert decrypt(ct2) == plaintext


def test_cipher_loads_from_env():
    cipher = _get_cipher()
    assert cipher is not None
