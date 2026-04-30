"""APNs client for sending push notifications via Apple's HTTP/2 API.

Uses JWT token-based authentication with a .p8 key.
"""

import json
import time
import logging
from pathlib import Path

import httpx
import jwt  # pyjwt — supports ES256 with the cryptography backend

from app.config import settings
from app.core.pem import PemConfigError, normalize_pem, validate_pem_loads

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
        """Load the APNs .p8 private key.

        Priority:
        1. `APNS_KEY_CONTENT` env var — raw .p8 contents (production via Railway)
        2. `APNS_KEY_PATH` env var — on-disk .p8 file (local development)

        The image must NOT bake the .p8 file in. `.dockerignore` excludes `keys/`.

        Normalizes CRLF and literal ``\\n`` sequences, ensures trailing
        newline. The 2026-04-29 audit (scheduler_audit.md) traced six
        recurring ``JWSError: MalformedFraming`` Sentry issues to env-var
        mangling that survived the old single ``.replace("\\\\n", "\\n")``
        call and got cached forever.
        """
        if self._private_key:
            return self._private_key

        # Production path: key injected via env var
        if settings.apns_key_content:
            self._private_key = normalize_pem(settings.apns_key_content)
            return self._private_key

        # Local dev path: read from on-disk file
        if settings.apns_key_path:
            key_path = Path(settings.apns_key_path)
            if not key_path.exists():
                raise FileNotFoundError(f"APNs .p8 key not found at {key_path}")
            self._private_key = normalize_pem(key_path.read_text())
            return self._private_key

        raise ValueError(
            "APNs key not configured — set APNS_KEY_CONTENT (production) "
            "or APNS_KEY_PATH (local dev)"
        )

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

        except httpx.HTTPError as e:
            # APNs returns structured errors as response bodies (handled above).
            # This catch is for transport-level failures: DNS, TLS, network,
            # timeout, and HTTP/2 frame errors.
            logger.error("APNs request failed: %s", str(e))
            return {"success": False, "status": 0, "error": str(e)}


# Singleton
apns_client = APNsClient()


def verify_apns_configured() -> None:
    """Fail fast at app startup if the APNs key is missing or malformed.

    Loads the key (which normalizes line endings) and asks `cryptography` to
    actually parse it. Misconfigured prod fails healthcheck and rolls back
    instead of waiting hours for the next scheduled morning brief to surface
    a corrupt PEM (the 2026-04-29 ``JWSError: MalformedFraming`` issues).

    No-op when neither APNS_KEY_CONTENT nor APNS_KEY_PATH is set —
    push-disabled environments (CI, some dev flows) should still boot.
    """
    if not (settings.apns_key_content or settings.apns_key_path):
        logger.info("APNs not configured (push disabled) — skipping verify")
        return
    pem = apns_client._load_private_key()
    try:
        validate_pem_loads(pem, label="APNs")
    except PemConfigError:
        # Drop the cached singleton so a subsequent fix + retry actually
        # re-reads the env, instead of returning the corrupt cached value.
        apns_client._private_key = None
        raise
