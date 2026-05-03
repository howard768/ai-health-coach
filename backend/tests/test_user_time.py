"""Tests for user-timezone-aware time helpers.

Pre-PR-G, `routers/meals.py` used naive `datetime.now()` for meal date and
classification. On Railway (UTC container), an EST user's 8pm dinner was
dated to the next calendar day, and "breakfast" auto-classification fired
at the wrong wall-clock hour for every user not in UTC.

These tests pin the behavioral fix:
  - `user_today_iso()` returns the date in the user's TZ, not the server TZ
  - `user_hour()` returns the hour in the user's TZ
  - Invalid TZ name falls back to UTC silently (don't crash user-visible
    endpoints; the misconfig surfaces via verify_secrets_configured)

Run: cd backend && uv run pytest tests/test_user_time.py -v
"""

import os
from datetime import datetime, timezone
from unittest.mock import patch

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-user-time-tests")

from app.core.time import user_now, user_today_iso, user_hour


def _fake_now(year: int, month: int, day: int, hour: int, minute: int = 0):
    """Build a fixed UTC datetime for `datetime.now(tz)` to return."""
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


# ── user_now ──────────────────────────────────────────────────────────────


def test_user_now_returns_tz_aware_datetime():
    result = user_now("America/New_York")
    assert result.tzinfo is not None


def test_user_now_falls_back_to_utc_on_invalid_tz():
    """A typo in user_timezone shouldn't crash user-facing endpoints."""
    result = user_now("Not/A/Real/Tz")
    assert result.tzinfo == timezone.utc


def test_user_now_uses_settings_default_when_tz_name_omitted(monkeypatch):
    """When called without args, picks up settings.user_timezone."""
    from app.config import settings
    monkeypatch.setattr(settings, "user_timezone", "America/New_York")
    result = user_now()
    # tzinfo string contains the zone name when ZoneInfo is used
    assert "New_York" in str(result.tzinfo) or str(result.tzinfo) == "America/New_York"


# ── user_today_iso, the meals.py date bug ────────────────────────────────


def test_user_today_iso_8pm_est_is_today_not_tomorrow():
    """The headline regression test: 8pm EST is still today's date even
    though it's already past midnight UTC."""
    # 2026-04-30 at 8pm EST = 2026-05-01 at 00:00 UTC
    fake_utc = _fake_now(2026, 5, 1, 0, 0)
    with patch("app.core.time.datetime") as mock_dt:
        mock_dt.now.return_value = fake_utc
        result = user_today_iso("America/New_York")
    # In EST that's still 2026-04-30 at 8pm
    assert result == "2026-04-30", (
        f"Expected EST-relative date 2026-04-30, got {result}. "
        "If this fails, the meals.py 'tomorrow' bug is back."
    )


def test_user_today_iso_noon_utc_aligns_with_user_tz():
    """Sanity: at noon UTC, an EST user is still on the same calendar day."""
    fake_utc = _fake_now(2026, 6, 15, 12, 0)
    with patch("app.core.time.datetime") as mock_dt:
        mock_dt.now.return_value = fake_utc
        result = user_today_iso("America/New_York")
    assert result == "2026-06-15"


def test_user_today_iso_invalid_tz_falls_back_to_utc():
    fake_utc = _fake_now(2026, 5, 1, 0, 30)
    with patch("app.core.time.datetime") as mock_dt:
        mock_dt.now.return_value = fake_utc
        result = user_today_iso("Bogus/Zone")
    # UTC fallback -> the UTC date
    assert result == "2026-05-01"


# ── user_hour, the meal classification bug ────────────────────────────────


def test_user_hour_8pm_est_returns_20_not_0():
    """Pre-PR-G, `datetime.now().hour` returned 0 (UTC midnight) when an EST
    user was eating dinner at 8pm. Meal classification then said "breakfast"
    at the wrong wall-clock time for every non-UTC user."""
    fake_utc = _fake_now(2026, 5, 1, 0, 0)  # midnight UTC = 8pm EST
    with patch("app.core.time.datetime") as mock_dt:
        mock_dt.now.return_value = fake_utc
        hour = user_hour("America/New_York")
    assert hour == 20


def test_user_hour_returns_int_in_range_0_23():
    hour = user_hour("America/New_York")
    assert isinstance(hour, int)
    assert 0 <= hour <= 23


def test_user_hour_invalid_tz_falls_back_to_utc():
    fake_utc = _fake_now(2026, 5, 1, 14, 30)
    with patch("app.core.time.datetime") as mock_dt:
        mock_dt.now.return_value = fake_utc
        hour = user_hour("Made/Up")
    assert hour == 14
