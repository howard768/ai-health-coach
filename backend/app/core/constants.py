"""Shared constants used across the coach engine, scheduler, notifications,
and routers. Centralized to prevent silent drift when one place changes a
threshold and others don't (P2-3 fix from the audit).
"""

from enum import IntEnum


class ReadinessThreshold(IntEnum):
    """Cutoffs for the Oura readiness score (0-100).

    Anything >= HIGH gets a "good to push" message.
    Between MODERATE and HIGH gets a "take it easy" message.
    Below MODERATE gets a "rest day" message.
    """

    HIGH = 67     # >= this → recovery_high / "Good for hard training"
    MODERATE = 34  # >= this → recovery_moderate / "Keep it easy"
    # Anything below MODERATE → recovery_low / "Rest today"


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
