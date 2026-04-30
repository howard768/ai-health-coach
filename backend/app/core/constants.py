"""Shared constants used across the coach engine, scheduler, notifications,
and routers. Centralized to prevent silent drift when one place changes a
threshold and others don't (P2-3 fix from the audit).
"""

from enum import IntEnum


# P3-3: Sentinel device token for the manual /test/send endpoint and any
# unit/integration tests. APNs short-circuits this token so we don't push
# to a real device, and the scheduler/notification jobs explicitly skip it
# so test data doesn't pollute notification analytics. If you need to add
# more test sentinels later, build a set instead.
TEST_DEVICE_TOKEN = "test_token_abc123"


class ReadinessThreshold(IntEnum):
    """Cutoffs for the Oura readiness score (0-100).

    Anything >= HIGH gets a "good to push" message.
    Between MODERATE and HIGH gets a "take it easy" message.
    Below MODERATE gets a "rest day" message.

    `ACTIVE_DAY_MIN` is the threshold for counting a day as "active" in the
    streak counter and weekly review aggregations. Pre-PR-J this was a bare
    `>= 50` literal in scheduler.py at two sites, drifting from the HIGH /
    MODERATE constants here. Centralized so a single place pins the rule.
    """

    HIGH = 67           # >= this → recovery_high / "Good for hard training"
    MODERATE = 34       # >= this → recovery_moderate / "Keep it easy"
    ACTIVE_DAY_MIN = 50 # >= this → counts as an "active day" for streak logic
    # Anything below MODERATE → recovery_low / "Rest today"


class StreakGoal(IntEnum):
    """Per-week active-day targets for the streak surface.

    Pre-PR-J this was hardcoded in `scheduler.py:streak_saver_job`. Centralized
    so the future per-user-streak-goal feature has one place to override.
    """

    DEFAULT_WEEKLY_TARGET = 5  # 5 active days/week is the v1 streak goal


class WeeklyReviewThreshold:
    """Cutoffs for the Sunday weekly-review summary.

    Three sleep-trend buckets (improving / stable / declining) by average
    sleep efficiency. Two workout-volume buckets (positive / tough week).
    Pre-PR-J these were inline literals in `scheduler.py:weekly_review_job`
    and `services/notification_content.py:212-214` with the SAME numbers
    duplicated. Drift between them was inevitable.
    """

    SLEEP_TREND_IMPROVING_MIN = 75  # avg efficiency > 75 → improving
    SLEEP_TREND_STABLE_MIN = 60     # avg efficiency > 60 → stable; below → declining
    POSITIVE_WEEK_WORKOUTS = 4      # >= 4 active days + improving sleep → "positive_week"
    TOUGH_WEEK_WORKOUTS = 3         # < 3 active days → "tough_week"


def readiness_level(score: float | int | None) -> str:
    """Return one of 'high', 'moderate', or 'low' for a readiness score.

    Returns 'unknown' if the score is None or 0 (sentinel for missing data).
    """
    if not score:
        return "unknown"
    if score >= ReadinessThreshold.HIGH:
        return "high"
    if score >= ReadinessThreshold.MODERATE:
        return "moderate"
    return "low"
