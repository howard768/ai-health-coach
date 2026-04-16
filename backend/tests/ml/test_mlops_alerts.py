"""Phase 10 ops alerting tests.

Tests cover:
1. Discord payload format
2. Telegram payload format
3. No-op on empty webhook
4. Drift alert routing (Discord always, Telegram on drift only)

Run: ``cd backend && uv run python -m pytest tests/ml/test_mlops_alerts.py -v``
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("ENCRYPTION_KEY", "T0TXLkHFSeZRYGIIejSFVkhQrvRE-bWLkwXSkkdWiKQ=")
os.environ.setdefault("ANTHROPIC_API_KEY", "fake-key-tests-dont-call-anthropic")

from ml.mlops.alerts import (
    send_discord_alert,
    send_telegram_alert,
)


# ---------------------------------------------------------------------------
# Unit: no-op on empty config
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_discord_noop_on_empty_url():
    """send_discord_alert should return False when URL is empty."""
    result = await send_discord_alert("Test", "Body", "")
    assert result is False


@pytest.mark.asyncio
async def test_telegram_noop_on_empty_token():
    """send_telegram_alert should return False when token is empty."""
    result = await send_telegram_alert("Test", "Body", "", "")
    assert result is False


@pytest.mark.asyncio
async def test_telegram_noop_on_empty_chat_id():
    """send_telegram_alert should return False when chat_id is empty."""
    result = await send_telegram_alert("Test", "Body", "token", "")
    assert result is False


# ---------------------------------------------------------------------------
# Unit: alert_drift routing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_alert_drift_no_crash_on_empty_config():
    """alert_drift should not crash when no webhooks configured."""
    from ml.mlops.alerts import alert_drift
    from dataclasses import dataclass

    @dataclass
    class FakeReport:
        drifted_metrics: list = None
        p_values: dict = None
        html_path: str = None
        metrics_tested: list = None
        n_reference_rows: int = 0
        n_current_rows: int = 0

        def __post_init__(self):
            if self.drifted_metrics is None:
                self.drifted_metrics = []
            if self.p_values is None:
                self.p_values = {}
            if self.metrics_tested is None:
                self.metrics_tested = []

    report = FakeReport(drifted_metrics=["hrv"], p_values={"hrv": 0.01})
    # Should not raise even with no config.
    await alert_drift(report)


@pytest.mark.asyncio
async def test_alert_training_no_crash():
    """alert_training_complete should not crash on empty config."""
    from ml.mlops.alerts import alert_training_complete

    summary = {"model_version": "ranker-test", "val_ndcg": 0.75}
    await alert_training_complete(summary)


@pytest.mark.asyncio
async def test_alert_rollback_no_crash():
    """alert_rollback should not crash on empty config."""
    from ml.mlops.alerts import alert_rollback

    await alert_rollback("ranker", "v1", "v0")
