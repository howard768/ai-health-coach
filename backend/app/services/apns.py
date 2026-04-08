"""APNs client for sending push notifications via Apple's HTTP/2 API.

Uses JWT token-based authentication with a .p8 key.
"""

import json
import time
import logging
from pathlib import Path

import httpx
from jose import jwt  # python-jose (already a dependency)

from app.config import settings

logger = logging.getLogger(__name__)

APNS_SANDBOX = "https://api.sandbox.push.apple.com"
APNS_PRODUCTION = "https://api.push.apple.com"


class APNsClient:
    """Sends push notifications to iOS devices via Apple Push Notification service."""

    def __init__(self):
        self._jwt_token: str | None = None
        self._jwt_issued_at: float = 0
        self._private_key: str | None = None

    def _load_private_key(self) -> str:
        if self._private_key:
            return self._private_key
        key_path = Path(settings.apns_key_path)
        if not key_path.exists():
            raise FileNotFoundError(f"APNs .p8 key not found at {key_path}")
        self._private_key = key_path.read_text()
        return self._private_key

    def _get_jwt_token(self) -> str:
        """Generate or return cached JWT. Refresh hourly per Apple requirement."""
        now = time.time()
        # Refresh if older than 50 minutes (buffer before 60-min expiry)
        if self._jwt_token and (now - self._jwt_issued_at) < 3000:
            return self._jwt_token

        private_key = self._load_private_key()
        headers = {
            "alg": "ES256",
            "kid": settings.apns_key_id,
        }
        payload = {
            "iss": settings.apns_team_id,
            "iat": int(now),
        }
        self._jwt_token = jwt.encode(payload, private_key, algorithm="ES256", headers=headers)
        self._jwt_issued_at = now
        return self._jwt_token

    @property
    def _base_url(self) -> str:
        if settings.apns_environment == "production":
            return APNS_PRODUCTION
        return APNS_SANDBOX

    async def send_push(
        self,
        device_token: str,
        title: str,
        body: str,
        *,
        subtitle: str | None = None,
        category: str | None = None,
        thread_id: str | None = None,
        interruption_level: str = "active",
        relevance_score: float = 0.5,
        collapse_id: str | None = None,
        badge: int | None = None,
        sound: str = "default",
        data: dict | None = None,
        media_url: str | None = None,
    ) -> dict:
        """Send a push notification via APNs.

        Returns dict with success status and APNs response.
        """
        # Build APNs payload
        alert = {"title": title, "body": body}
        if subtitle:
            alert["subtitle"] = subtitle

        aps = {
            "alert": alert,
            "sound": sound,
            "interruption-level": interruption_level,
            "relevance-score": relevance_score,
        }
        if category:
            aps["category"] = category
        if thread_id:
            aps["thread-id"] = thread_id
        if badge is not None:
            aps["badge"] = badge
        if media_url:
            aps["mutable-content"] = 1

        payload = {"aps": aps}
        if data:
            payload.update(data)
        if media_url:
            payload["media_url"] = media_url

        # Build request
        url = f"{self._base_url}/3/device/{device_token}"
        token = self._get_jwt_token()
        headers = {
            "authorization": f"bearer {token}",
            "apns-topic": settings.apns_bundle_id,
            "apns-push-type": "alert",
            "apns-priority": "10" if interruption_level == "time-sensitive" else "5",
        }
        if collapse_id:
            headers["apns-collapse-id"] = collapse_id
        if interruption_level == "time-sensitive":
            headers["apns-priority"] = "10"

        payload_bytes = json.dumps(payload).encode("utf-8")
        if len(payload_bytes) > 4096:
            logger.warning("APNs payload exceeds 4KB limit: %d bytes", len(payload_bytes))

        try:
            async with httpx.AsyncClient(http2=True) as client:
                response = await client.post(url, content=payload_bytes, headers=headers)

            if response.status_code == 200:
                logger.info("Push sent to %s...%s", device_token[:8], device_token[-4:])
                return {"success": True, "status": 200}
            else:
                error_body = response.text
                logger.error(
                    "APNs error %d for %s...%s: %s",
                    response.status_code,
                    device_token[:8],
                    device_token[-4:],
                    error_body,
                )
                return {
                    "success": False,
                    "status": response.status_code,
                    "error": error_body,
                }

        except Exception as e:
            logger.error("APNs request failed: %s", str(e))
            return {"success": False, "status": 0, "error": str(e)}


# Singleton
apns_client = APNsClient()
