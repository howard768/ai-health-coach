import httpx
from datetime import date, timedelta

from app.config import settings
from app.core.http import DEFAULT_TIMEOUT

OURA_AUTH_URL = "https://cloud.ouraring.com/oauth/authorize"
OURA_TOKEN_URL = "https://api.ouraring.com/oauth/token"
OURA_API_BASE = "https://api.ouraring.com/v2/usercollection"


class OuraClient:
    def __init__(self, access_token: str | None = None):
        self.access_token = access_token

    def get_auth_url(self) -> str:
        return (
            f"{OURA_AUTH_URL}"
            f"?response_type=code"
            f"&client_id={settings.oura_client_id}"
            f"&redirect_uri={settings.oura_redirect_uri}"
            f"&scope=daily heartrate workout tag session spo2 ring_configuration stress"
        )

    async def exchange_code(self, code: str) -> dict:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            response = await client.post(
                OURA_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": settings.oura_client_id,
                    "client_secret": settings.oura_client_secret,
                    "redirect_uri": settings.oura_redirect_uri,
                },
            )
            response.raise_for_status()
            return response.json()

    async def get_daily_sleep(self, start_date: date | None = None, end_date: date | None = None) -> dict:
        if not start_date:
            start_date = date.today() - timedelta(days=7)
        if not end_date:
            end_date = date.today()

        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            response = await client.get(
                f"{OURA_API_BASE}/daily_sleep",
                headers={"Authorization": f"Bearer {self.access_token}"},
                params={"start_date": str(start_date), "end_date": str(end_date)},
            )
            response.raise_for_status()
            return response.json()

    async def get_sleep_sessions(self, start_date: date | None = None, end_date: date | None = None) -> dict:
        """Get detailed sleep session data (durations, stages, timing)."""
        if not start_date:
            start_date = date.today() - timedelta(days=7)
        if not end_date:
            end_date = date.today()

        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            response = await client.get(
                f"{OURA_API_BASE}/sleep",
                headers={"Authorization": f"Bearer {self.access_token}"},
                params={"start_date": str(start_date), "end_date": str(end_date)},
            )
            response.raise_for_status()
            return response.json()

    async def get_daily_readiness(self, start_date: date | None = None, end_date: date | None = None) -> dict:
        if not start_date:
            start_date = date.today() - timedelta(days=7)
        if not end_date:
            end_date = date.today()

        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            response = await client.get(
                f"{OURA_API_BASE}/daily_readiness",
                headers={"Authorization": f"Bearer {self.access_token}"},
                params={"start_date": str(start_date), "end_date": str(end_date)},
            )
            response.raise_for_status()
            return response.json()

    async def refresh_access_token(self, refresh_token: str) -> dict:
        """Refresh an expired Oura access token using OAuth2 refresh flow."""
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            response = await client.post(
                OURA_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": settings.oura_client_id,
                    "client_secret": settings.oura_client_secret,
                },
            )
            response.raise_for_status()
            return response.json()

    async def get_personal_info(self) -> dict:
        """Fetch the user's Oura account info (id, age, weight, etc.).

        MEL-45 part 2: called from `oura_callback` to capture the Oura user ID
        for `OuraToken.oura_user_id` so the webhook receiver can route incoming
        events to the correct Meld user. Oura's webhook payload sends
        `body["user_id"]` matching this endpoint's `id` field.

        https://cloud.ouraring.com/v2/docs#operation/personal_info_v2_usercollection_personal_info_get
        """
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            response = await client.get(
                f"{OURA_API_BASE}/personal_info",
                headers={"Authorization": f"Bearer {self.access_token}"},
            )
            response.raise_for_status()
            return response.json()

    async def get_heartrate(self, start_date: date | None = None, end_date: date | None = None) -> dict:
        if not start_date:
            start_date = date.today() - timedelta(days=1)
        if not end_date:
            end_date = date.today()

        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            response = await client.get(
                f"{OURA_API_BASE}/heartrate",
                headers={"Authorization": f"Bearer {self.access_token}"},
                params={
                    "start_datetime": f"{start_date}T00:00:00+00:00",
                    "end_datetime": f"{end_date}T23:59:59+00:00",
                },
            )
            response.raise_for_status()
            return response.json()
