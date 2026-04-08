import httpx
from datetime import date, timedelta

from app.config import settings

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
        async with httpx.AsyncClient() as client:
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

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{OURA_API_BASE}/daily_sleep",
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

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{OURA_API_BASE}/daily_readiness",
                headers={"Authorization": f"Bearer {self.access_token}"},
                params={"start_date": str(start_date), "end_date": str(end_date)},
            )
            response.raise_for_status()
            return response.json()

    async def get_heartrate(self, start_date: date | None = None, end_date: date | None = None) -> dict:
        if not start_date:
            start_date = date.today() - timedelta(days=1)
        if not end_date:
            end_date = date.today()

        async with httpx.AsyncClient() as client:
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
