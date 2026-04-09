"""Peloton API client.

Unofficial API at api.onepeloton.com. Session cookie authentication
(username/password → session_id). NOT OAuth.

Risk: Unofficial API, could change without notice.
All calls wrapped in try/catch for graceful degradation.
"""

import logging
from datetime import date, timedelta

import httpx

logger = logging.getLogger("meld.peloton")

PELOTON_API = "https://api.onepeloton.com"


class PelotonClient:
    """Interacts with Peloton's unofficial API."""

    def __init__(self, session_id: str | None = None, user_id: str | None = None):
        self.session_id = session_id
        self.peloton_user_id = user_id

    async def login(self, username: str, password: str) -> dict:
        """Authenticate with Peloton and get session cookie.

        Returns dict with session_id and user_id.
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PELOTON_API}/auth/login",
                json={"username_or_email": username, "password": password},
            )
            response.raise_for_status()
            data = response.json()

        self.session_id = data.get("session_id")
        self.peloton_user_id = data.get("user_id")

        return {
            "session_id": self.session_id,
            "user_id": self.peloton_user_id,
        }

    async def get_workouts(self, limit: int = 20, page: int = 0) -> dict:
        """Get recent workouts for the authenticated user."""
        if not self.session_id or not self.peloton_user_id:
            raise ValueError("Not authenticated. Call login() first.")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{PELOTON_API}/api/user/{self.peloton_user_id}/workouts",
                params={
                    "joins": "ride,ride.instructor",
                    "limit": limit,
                    "page": page,
                },
                cookies={"peloton_session_id": self.session_id},
                headers={"Peloton-Platform": "web"},
            )
            response.raise_for_status()
            return response.json()

    async def get_workout_details(self, workout_id: str) -> dict:
        """Get detailed metrics for a specific workout."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{PELOTON_API}/api/workout/{workout_id}/performance_graph",
                params={"every_n": 5},  # Sample every 5 seconds
                cookies={"peloton_session_id": self.session_id},
                headers={"Peloton-Platform": "web"},
            )
            response.raise_for_status()
            return response.json()

    def parse_workout(self, workout: dict) -> dict:
        """Normalize a Peloton workout to our WorkoutRecord format."""
        ride = workout.get("ride", {})
        instructor = ride.get("instructor", {})

        # Determine workout type from fitness_discipline
        discipline = workout.get("fitness_discipline", "cycling")
        workout_type_map = {
            "cycling": "cycling",
            "running": "running",
            "strength": "strength",
            "yoga": "yoga",
            "meditation": "meditation",
            "stretching": "stretching",
            "walking": "walking",
            "bootcamp": "bootcamp",
            "rowing": "rowing",
        }
        workout_type = workout_type_map.get(discipline, discipline)

        return {
            "peloton_workout_id": workout.get("id"),
            "workout_type": workout_type,
            "duration_seconds": ride.get("duration", 0),
            "calories": workout.get("total_work", 0) // 1000 if workout.get("total_work") else None,
            "avg_heart_rate": None,  # Requires performance_graph call
            "max_heart_rate": None,
            "avg_output": None,  # Watts, cycling-specific
            "instructor": instructor.get("name"),
            "title": ride.get("title"),
            "created_at": workout.get("created_at"),
        }
