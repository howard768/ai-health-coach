"""Garmin Connect API client.

Uses the garminconnect Python library (SSO-based authentication).
The library is synchronous — wrap calls in asyncio.to_thread() for async backend.
"""

import logging
import asyncio
from datetime import date, timedelta

logger = logging.getLogger("meld.garmin")


class GarminClient:
    """Wraps the garminconnect library for async usage."""

    def __init__(self):
        self._client = None

    async def login(self, username: str, password: str) -> dict:
        """Authenticate with Garmin Connect via SSO."""
        try:
            from garminconnect import Garmin
        except ImportError:
            logger.error("garminconnect library not installed")
            raise RuntimeError("garminconnect package not installed. Run: uv add garminconnect")

        def _login():
            client = Garmin(username, password)
            client.login()
            return client

        self._client = await asyncio.to_thread(_login)
        return {"status": "connected", "display_name": self._client.display_name}

    async def get_steps(self, target_date: date) -> dict | None:
        """Get daily step count."""
        if not self._client:
            return None
        try:
            return await asyncio.to_thread(
                self._client.get_steps_data, target_date.isoformat()
            )
        except Exception as e:
            logger.error("Garmin steps error: %s", e)
            return None

    async def get_heart_rate(self, target_date: date) -> dict | None:
        """Get daily heart rate data."""
        if not self._client:
            return None
        try:
            return await asyncio.to_thread(
                self._client.get_heart_rates, target_date.isoformat()
            )
        except Exception as e:
            logger.error("Garmin heart rate error: %s", e)
            return None

    async def get_sleep(self, target_date: date) -> dict | None:
        """Get sleep data."""
        if not self._client:
            return None
        try:
            return await asyncio.to_thread(
                self._client.get_sleep_data, target_date.isoformat()
            )
        except Exception as e:
            logger.error("Garmin sleep error: %s", e)
            return None

    async def get_stress(self, target_date: date) -> dict | None:
        """Get stress data."""
        if not self._client:
            return None
        try:
            return await asyncio.to_thread(
                self._client.get_stress_data, target_date.isoformat()
            )
        except Exception as e:
            logger.error("Garmin stress error: %s", e)
            return None

    async def get_body_battery(self, target_date: date) -> dict | None:
        """Get body battery data."""
        if not self._client:
            return None
        try:
            return await asyncio.to_thread(
                self._client.get_body_battery, target_date.isoformat()
            )
        except Exception as e:
            logger.error("Garmin body battery error: %s", e)
            return None

    async def get_activities(self, start: int = 0, limit: int = 20) -> list:
        """Get recent activities/workouts."""
        if not self._client:
            return []
        try:
            return await asyncio.to_thread(
                self._client.get_activities, start, limit
            )
        except Exception as e:
            logger.error("Garmin activities error: %s", e)
            return []
