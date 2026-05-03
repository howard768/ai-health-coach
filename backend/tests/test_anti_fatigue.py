"""Tests for the anti-fatigue notification gate.

Covers each individual gate (preference, quiet hours, daily budget,
auto-disable, throttle) plus the orchestrator `can_send`.

Audit follow-up: docs/comprehensive-scan-2026-04-30.md flagged this as
one of the four backend services with no test coverage despite owning
a 3-step execution flow.

Run: cd backend && uv run python -m pytest tests/test_anti_fatigue.py -v
"""

from __future__ import annotations

import os
import pytest
import pytest_asyncio

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("ENCRYPTION_KEY", "T0TXLkHFSeZRYGIIejSFVkhQrvRE-bWLkwXSkkdWiKQ=")
os.environ.setdefault("ANTHROPIC_API_KEY", "fake-key-tests-dont-call-anthropic")

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.database import Base
from app.models.notification import NotificationPreference, NotificationRecord
from app.services import anti_fatigue


USER = "test-user-1"


@pytest_asyncio.fixture
async def db():
    """In-memory async SQLite session with all tables created."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


def _record(category: str, sent_at: datetime, opened: bool = False) -> NotificationRecord:
    return NotificationRecord(
        user_id=USER,
        category=category,
        title="t",
        body="b",
        sent_at=sent_at,
        opened_at=sent_at + timedelta(minutes=5) if opened else None,
    )


def _utc_naive_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# check_preference --------------------------------------------------------


@pytest.mark.asyncio
async def test_preference_returns_true_when_no_pref_row(db):
    """Default state for a brand-new user is everything-on."""
    assert await anti_fatigue.check_preference(db, USER, "morning_brief") is True


@pytest.mark.asyncio
async def test_preference_returns_true_when_category_enabled(db):
    db.add(NotificationPreference(user_id=USER, morning_brief=True))
    await db.commit()
    assert await anti_fatigue.check_preference(db, USER, "morning_brief") is True


@pytest.mark.asyncio
async def test_preference_returns_false_when_category_disabled(db):
    db.add(NotificationPreference(user_id=USER, morning_brief=False))
    await db.commit()
    assert await anti_fatigue.check_preference(db, USER, "morning_brief") is False


@pytest.mark.asyncio
async def test_preference_returns_true_for_unknown_category(db):
    """A category name that isn't a column on the preferences row defaults
    to allowed; this matches the existing per-category opt-in design."""
    db.add(NotificationPreference(user_id=USER))
    await db.commit()
    assert await anti_fatigue.check_preference(db, USER, "nonexistent_category") is True


# check_quiet_hours -------------------------------------------------------


@pytest.mark.asyncio
async def test_quiet_hours_returns_true_when_no_pref_row(db):
    assert await anti_fatigue.check_quiet_hours(db, USER) is True


@pytest.mark.asyncio
async def test_quiet_hours_blocks_inside_wrapping_window(db, monkeypatch):
    """Default quiet hours 22:00-07:00 wrap midnight; 23:00 is inside."""
    db.add(NotificationPreference(user_id=USER, quiet_hours_start="22:00", quiet_hours_end="07:00"))
    await db.commit()

    fake = datetime(2026, 5, 2, 23, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(anti_fatigue, "_user_now", lambda: fake)
    assert await anti_fatigue.check_quiet_hours(db, USER) is False


@pytest.mark.asyncio
async def test_quiet_hours_allows_outside_wrapping_window(db, monkeypatch):
    db.add(NotificationPreference(user_id=USER, quiet_hours_start="22:00", quiet_hours_end="07:00"))
    await db.commit()

    fake = datetime(2026, 5, 2, 14, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(anti_fatigue, "_user_now", lambda: fake)
    assert await anti_fatigue.check_quiet_hours(db, USER) is True


@pytest.mark.asyncio
async def test_quiet_hours_blocks_inside_simple_window(db, monkeypatch):
    """Non-wrapping window e.g. 01:00-06:00."""
    db.add(NotificationPreference(user_id=USER, quiet_hours_start="01:00", quiet_hours_end="06:00"))
    await db.commit()

    fake = datetime(2026, 5, 2, 3, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(anti_fatigue, "_user_now", lambda: fake)
    assert await anti_fatigue.check_quiet_hours(db, USER) is False


# check_daily_budget ------------------------------------------------------


@pytest.mark.asyncio
async def test_budget_allows_when_under_cap(db):
    now = _utc_naive_now()
    for i in range(anti_fatigue.MAX_DAILY_NOTIFICATIONS - 1):
        db.add(_record("morning_brief", now - timedelta(minutes=i)))
    await db.commit()
    assert await anti_fatigue.check_daily_budget(db, USER) is True


@pytest.mark.asyncio
async def test_budget_blocks_at_cap(db):
    now = _utc_naive_now()
    for i in range(anti_fatigue.MAX_DAILY_NOTIFICATIONS):
        db.add(_record("morning_brief", now - timedelta(minutes=i)))
    await db.commit()
    assert await anti_fatigue.check_daily_budget(db, USER) is False


@pytest.mark.asyncio
async def test_budget_ignores_yesterday(db):
    """Records from before the user-tz day boundary do not count."""
    yesterday = _utc_naive_now() - timedelta(days=1, hours=2)
    for _ in range(anti_fatigue.MAX_DAILY_NOTIFICATIONS):
        db.add(_record("morning_brief", yesterday))
    await db.commit()
    assert await anti_fatigue.check_daily_budget(db, USER) is True


# check_throttle ----------------------------------------------------------


@pytest.mark.asyncio
async def test_throttle_allows_when_history_short(db):
    """Fewer than 3 prior records means the throttle has nothing to fire on."""
    now = _utc_naive_now()
    db.add(_record("coaching_nudge", now))
    await db.commit()
    assert await anti_fatigue.check_throttle(db, USER, "coaching_nudge") is True


@pytest.mark.asyncio
async def test_throttle_allows_when_recent_was_opened(db):
    """If any of the last 3 was opened, throttle is not triggered."""
    now = _utc_naive_now()
    db.add(_record("coaching_nudge", now - timedelta(hours=2)))
    db.add(_record("coaching_nudge", now - timedelta(hours=1), opened=True))
    db.add(_record("coaching_nudge", now))
    await db.commit()
    assert await anti_fatigue.check_throttle(db, USER, "coaching_nudge") is True


@pytest.mark.asyncio
async def test_throttle_skips_every_other_when_three_consecutive_ignored(db):
    """3 consecutive ignored notifications + even total -> skip."""
    now = _utc_naive_now()
    for i in range(4):
        db.add(_record("coaching_nudge", now - timedelta(hours=i)))
    await db.commit()
    # 4 records total, 4 % 2 == 0 -> should_skip True -> can_send False
    assert await anti_fatigue.check_throttle(db, USER, "coaching_nudge") is False


@pytest.mark.asyncio
async def test_throttle_allows_on_odd_count_after_three_ignored(db):
    """Same condition but odd total count means we DO send (every-other pattern)."""
    now = _utc_naive_now()
    for i in range(3):
        db.add(_record("coaching_nudge", now - timedelta(hours=i)))
    await db.commit()
    # 3 records, 3 % 2 == 1 -> should_skip False -> can send
    assert await anti_fatigue.check_throttle(db, USER, "coaching_nudge") is True


# check_auto_disable ------------------------------------------------------


@pytest.mark.asyncio
async def test_auto_disable_inactive_when_history_short(db):
    """Fewer than 7 records leaves the gate open."""
    now = _utc_naive_now()
    for _ in range(6):
        db.add(_record("coaching_nudge", now))
    await db.commit()
    assert await anti_fatigue.check_auto_disable(db, USER, "coaching_nudge") is True


@pytest.mark.asyncio
async def test_auto_disable_allows_when_any_recent_opened(db):
    """If even one of the last 7 was opened, the user is engaged enough."""
    now = _utc_naive_now()
    for i in range(7):
        db.add(_record("coaching_nudge", now - timedelta(hours=i), opened=(i == 3)))
    await db.commit()
    assert await anti_fatigue.check_auto_disable(db, USER, "coaching_nudge") is True


@pytest.mark.asyncio
async def test_auto_disable_disables_category_after_seven_consecutive_ignored(db):
    """7 ignored in a row + a preferences row -> writes False to that category."""
    db.add(NotificationPreference(user_id=USER, coaching_nudge=True))
    now = _utc_naive_now()
    for i in range(7):
        db.add(_record("coaching_nudge", now - timedelta(hours=i)))
    await db.commit()

    result = await anti_fatigue.check_auto_disable(db, USER, "coaching_nudge")
    assert result is False

    pref = (await db.execute(
        __import__("sqlalchemy").select(NotificationPreference)
        .where(NotificationPreference.user_id == USER)
    )).scalar_one()
    assert pref.coaching_nudge is False


# can_send (integration) --------------------------------------------------


@pytest.mark.asyncio
async def test_can_send_returns_false_when_preference_disabled(db, monkeypatch):
    db.add(NotificationPreference(user_id=USER, morning_brief=False))
    await db.commit()
    fake = datetime(2026, 5, 2, 14, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(anti_fatigue, "_user_now", lambda: fake)
    assert await anti_fatigue.can_send(db, USER, "morning_brief") is False


@pytest.mark.asyncio
async def test_can_send_returns_true_for_clean_state(db, monkeypatch):
    """No prior notifications + outside quiet hours + default prefs -> allowed."""
    fake = datetime(2026, 5, 2, 14, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(anti_fatigue, "_user_now", lambda: fake)
    assert await anti_fatigue.can_send(db, USER, "morning_brief") is True
