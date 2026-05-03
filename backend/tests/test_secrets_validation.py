"""Tests for `verify_secrets_configured` startup check.

This validation is intentionally fail-fast in production environments
(secrets recover in seconds, not days, so coupling deploy success is
correct) and warn-and-continue in development. The behavioral matrix:

| env=production              | env=development              |
| --------------------------- | ---------------------------- |
| empty JWT/ENCRYPTION → raise | empty JWT/ENCRYPTION → info  |
| empty Anthropic → log error | empty Anthropic → info       |
| 'change-me' app_secret → log| 'change-me' app_secret → info|
| invalid apns_env → log error| invalid apns_env → log error |
| all set → info, no error    | all set → info, no error     |

Run: cd backend && uv run pytest tests/test_secrets_validation.py -v
"""

import logging
import os

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-secrets-validation-tests")

from app.config import settings
from app.core.secrets import SecretConfigError, verify_secrets_configured


def _fully_set(monkeypatch):
    """Helper: set every secret to a non-empty value so only the var
    under test is empty/sentinel."""
    monkeypatch.setattr(settings, "jwt_secret_key", "x" * 32)
    monkeypatch.setattr(settings, "encryption_key", "x" * 32)
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-test")
    monkeypatch.setattr(settings, "app_secret_key", "real-secret")
    monkeypatch.setattr(settings, "apns_environment", "production")


# ── Production: critical secrets must fail-fast ─────────────────────────────


def test_prod_empty_jwt_secret_raises(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    _fully_set(monkeypatch)
    monkeypatch.setattr(settings, "jwt_secret_key", "")
    with pytest.raises(SecretConfigError, match="JWT_SECRET_KEY"):
        verify_secrets_configured()


def test_prod_whitespace_jwt_secret_raises(monkeypatch):
    """Whitespace-only is the same Railway-UI footgun as missing, treat the same."""
    monkeypatch.setattr(settings, "app_env", "production")
    _fully_set(monkeypatch)
    monkeypatch.setattr(settings, "jwt_secret_key", "   \n\t  ")
    with pytest.raises(SecretConfigError, match="JWT_SECRET_KEY"):
        verify_secrets_configured()


def test_prod_empty_encryption_key_raises(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    _fully_set(monkeypatch)
    monkeypatch.setattr(settings, "encryption_key", "")
    with pytest.raises(SecretConfigError, match="ENCRYPTION_KEY"):
        verify_secrets_configured()


def test_prod_both_critical_missing_lists_both(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    _fully_set(monkeypatch)
    monkeypatch.setattr(settings, "jwt_secret_key", "")
    monkeypatch.setattr(settings, "encryption_key", "")
    with pytest.raises(SecretConfigError) as exc_info:
        verify_secrets_configured()
    assert "JWT_SECRET_KEY" in str(exc_info.value)
    assert "ENCRYPTION_KEY" in str(exc_info.value)


# ── Production: non-critical secrets log error but don't raise ──────────────


def test_prod_empty_anthropic_logs_error_no_raise(monkeypatch, caplog):
    monkeypatch.setattr(settings, "app_env", "production")
    _fully_set(monkeypatch)
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    with caplog.at_level(logging.ERROR, logger="meld.secrets"):
        verify_secrets_configured()  # must not raise
    error_records = [r for r in caplog.records if r.levelname == "ERROR"]
    assert any("ANTHROPIC_API_KEY" in r.getMessage() for r in error_records)


def test_prod_change_me_app_secret_logs_error(monkeypatch, caplog):
    monkeypatch.setattr(settings, "app_env", "production")
    _fully_set(monkeypatch)
    monkeypatch.setattr(settings, "app_secret_key", "change-me")
    with caplog.at_level(logging.ERROR, logger="meld.secrets"):
        verify_secrets_configured()  # must not raise
    error_records = [r for r in caplog.records if r.levelname == "ERROR"]
    assert any("change-me" in r.getMessage() for r in error_records)


def test_prod_invalid_apns_env_logs_error(monkeypatch, caplog):
    monkeypatch.setattr(settings, "app_env", "production")
    _fully_set(monkeypatch)
    monkeypatch.setattr(settings, "apns_environment", "prod")  # typo
    with caplog.at_level(logging.ERROR, logger="meld.secrets"):
        verify_secrets_configured()  # must not raise
    error_records = [r for r in caplog.records if r.levelname == "ERROR"]
    assert any("APNS_ENVIRONMENT" in r.getMessage() for r in error_records)


def test_prod_apns_env_sandbox_is_valid(monkeypatch, caplog):
    monkeypatch.setattr(settings, "app_env", "production")
    _fully_set(monkeypatch)
    monkeypatch.setattr(settings, "apns_environment", "sandbox")
    with caplog.at_level(logging.ERROR, logger="meld.secrets"):
        verify_secrets_configured()
    error_records = [r for r in caplog.records if r.levelname == "ERROR"]
    assert not error_records


# ── Production: fully configured = silent (no errors) ───────────────────────


def test_prod_fully_configured_no_errors(monkeypatch, caplog):
    monkeypatch.setattr(settings, "app_env", "production")
    _fully_set(monkeypatch)
    with caplog.at_level(logging.ERROR, logger="meld.secrets"):
        verify_secrets_configured()
    error_records = [r for r in caplog.records if r.levelname == "ERROR"]
    assert not error_records


# ── Development: never raises, even with empty secrets ──────────────────────


def test_dev_empty_critical_secrets_does_not_raise(monkeypatch):
    """Development mode: missing JWT + ENCRYPTION = informational, not fatal.
    Local devs run with SQLite + no real keys; that's expected."""
    monkeypatch.setattr(settings, "app_env", "development")
    _fully_set(monkeypatch)
    monkeypatch.setattr(settings, "jwt_secret_key", "")
    monkeypatch.setattr(settings, "encryption_key", "")
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    monkeypatch.setattr(settings, "app_secret_key", "change-me")
    # No raise expected
    verify_secrets_configured()


def test_dev_empty_secrets_no_error_logs(monkeypatch, caplog):
    monkeypatch.setattr(settings, "app_env", "development")
    _fully_set(monkeypatch)
    monkeypatch.setattr(settings, "jwt_secret_key", "")
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    monkeypatch.setattr(settings, "app_secret_key", "change-me")
    with caplog.at_level(logging.ERROR, logger="meld.secrets"):
        verify_secrets_configured()
    error_records = [r for r in caplog.records if r.levelname == "ERROR"]
    # APNS_ENVIRONMENT 'production' is fine; no other errors expected in dev.
    assert not error_records


def test_dev_invalid_apns_env_still_logs_error(monkeypatch, caplog):
    """APNS_ENVIRONMENT typo is a footgun even in dev (silently routes pushes
    to the wrong cluster); log loudly regardless of env."""
    monkeypatch.setattr(settings, "app_env", "development")
    _fully_set(monkeypatch)
    monkeypatch.setattr(settings, "apns_environment", "prod")
    with caplog.at_level(logging.ERROR, logger="meld.secrets"):
        verify_secrets_configured()
    error_records = [r for r in caplog.records if r.levelname == "ERROR"]
    assert any("APNS_ENVIRONMENT" in r.getMessage() for r in error_records)
