"""Ops alerting for the Signal Engine.

Discord for all ops notifications (drift detected, training complete,
experiment finished). Telegram for critical alerts only (model failures,
rollback events, drift in production metrics).

All alerts are best-effort: no-op when webhook URLs are empty (dev/CI),
no crash on API failure. Errors are logged but never propagated.

All imports (httpx) are lazy inside function bodies per the cold-boot contract.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Low-level senders
# ---------------------------------------------------------------------------


async def send_discord_alert(title: str, body: str, webhook_url: str) -> bool:
    """POST to a Discord Incoming Webhook. Returns True on success."""
    if not webhook_url:
        return False

    import httpx

    payload = {
        "embeds": [
            {
                "title": title,
                "description": body[:4096],  # Discord embed limit
                "color": 0xFF6600,  # orange
            }
        ]
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(webhook_url, json=payload)
            resp.raise_for_status()
        return True
    except Exception:
        logger.debug("Discord alert failed", exc_info=True)
        return False


async def send_telegram_alert(title: str, body: str, bot_token: str, chat_id: str) -> bool:
    """POST to the Telegram Bot API sendMessage endpoint. Returns True on success."""
    if not bot_token or not chat_id:
        return False

    import httpx

    text = f"*{title}*\n{body}"
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text[:4096],  # Telegram message limit
        "parse_mode": "Markdown",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
        return True
    except Exception:
        logger.debug("Telegram alert failed", exc_info=True)
        return False


# ---------------------------------------------------------------------------
# High-level alert functions
# ---------------------------------------------------------------------------


def _get_alert_config() -> tuple[str, str, str]:
    """Return (discord_url, telegram_token, telegram_chat_id) from MLSettings."""
    from ml.config import get_ml_settings

    settings = get_ml_settings()
    return (
        settings.discord_ops_webhook_url,
        settings.telegram_bot_token,
        settings.telegram_chat_id,
    )


async def alert_drift(report: object) -> None:
    """Alert on drift detection. Discord always, Telegram if drifted metrics found."""
    discord_url, tg_token, tg_chat = _get_alert_config()

    drifted = getattr(report, "drifted_metrics", [])
    p_values = getattr(report, "p_values", {})
    html_path = getattr(report, "html_path", None)

    if not drifted:
        # No drift: info-level Discord only.
        body = (
            f"Daily drift check: no drift detected.\n"
            f"Metrics tested: {getattr(report, 'metrics_tested', [])}\n"
            f"Ref rows: {getattr(report, 'n_reference_rows', 0)}, "
            f"Current rows: {getattr(report, 'n_current_rows', 0)}"
        )
        await send_discord_alert("Drift Check: Clear", body, discord_url)
        return

    # Drift detected: both Discord + Telegram.
    p_str = ", ".join(f"{k}: p={v:.4f}" for k, v in p_values.items() if k in drifted)
    body = (
        f"Drifted metrics: {', '.join(drifted)}\n"
        f"P-values: {p_str}\n"
        f"Report: {html_path or 'no HTML available'}"
    )
    await send_discord_alert("Drift Detected", body, discord_url)
    await send_telegram_alert("Drift Detected", body, tg_token, tg_chat)


async def alert_training_complete(summary: dict) -> None:
    """Alert on training completion. Discord only (info-level)."""
    discord_url, _, _ = _get_alert_config()

    body = (
        f"Model: {summary.get('model_version', 'unknown')}\n"
        f"Samples: {summary.get('train_samples', 0)}\n"
        f"Val NDCG: {summary.get('val_ndcg', 0.0):.4f}\n"
        f"CoreML: {summary.get('coreml_exported', False)}\n"
        f"R2: {summary.get('r2_uploaded', False)}"
    )
    await send_discord_alert("Ranker Training Complete", body, discord_url)


async def alert_rollback(model_type: str, from_version: str, to_version: str) -> None:
    """Alert on model rollback. Both Discord + Telegram (critical)."""
    discord_url, tg_token, tg_chat = _get_alert_config()

    body = (
        f"Model type: {model_type}\n"
        f"Rolled back from: {from_version}\n"
        f"Rolled back to: {to_version}"
    )
    await send_discord_alert("Model Rollback", body, discord_url)
    await send_telegram_alert("Model Rollback", body, tg_token, tg_chat)
