"""Specialized notification content generators for each category.

Each generator produces short-form, privacy-safe notification content
using the CoachEngine pipeline. All follow the wiki rules:
- No raw metrics in title or body (privacy on lock screen)
- No emoji
- 4th grade reading level
- Evidence-bound: reference data patterns, not raw numbers
"""

import json
import logging
from datetime import datetime

from app.services.coach_engine import CoachEngine
from app.services.notification_media import generate_recovery_badge

logger = logging.getLogger("meld.notifications.content")

# Shared rules injected into every prompt
SHARED_RULES = """STRICT RULES — violating any is a failure:
1. NEVER include numbers, percentages, scores, or raw metrics. These are private health data visible on the lock screen.
2. NEVER use emoji. Not one. Zero emoji anywhere.
3. 4th grade reading level. Short sentences. Simple words.
4. Be warm and human, not robotic."""

COACHING_NUDGE_PROMPT = """Generate a push notification with a cross-domain health insight.

{shared_rules}

ADDITIONAL RULES:
- Title: max 40 chars. Intriguing, not generic. Make the user want to tap.
- Body: max 120 chars. Connect TWO health domains (e.g., food→sleep, exercise→recovery). Reference a PATTERN, not a single data point.
- Frame as a personal discovery: "Your data shows..." or "We noticed..."
- Include ONE actionable suggestion.

GOOD examples:
- Title: "Your coach spotted something" / Body: "On days you eat dinner earlier, your sleep is noticeably deeper. Worth trying tonight."
- Title: "A pattern in your data" / Body: "Your recovery tends to be stronger after rest days. Your body might need one soon."

BAD examples:
- "Your HRV was 68ms" ← raw number
- "Tip of the day" ← generic, not data-driven

Health context (reference only, do NOT put numbers in the output): {health_data}
Known cross-domain connections: {connections}

Respond in EXACTLY this JSON format and nothing else:
{{"title": "...", "body": "..."}}"""

BEDTIME_COACHING_PROMPT = """Generate a push notification for a bedtime wind-down reminder.

{shared_rules}

ADDITIONAL RULES:
- Title: max 40 chars. Gentle, calming tone. No urgency.
- Body: max 100 chars. One specific wind-down suggestion based on today's data.
- If the user had a hard day (high strain, poor recovery), suggest extra rest.
- If the user had a good day, reinforce the positive habits.
- Tone: like a caring friend, not a drill sergeant.

GOOD examples:
- Title: "Time to wind down" / Body: "You had a big day. A few deep breaths before bed could help tonight."
- Title: "Almost bedtime" / Body: "Great recovery today. Keep the momentum with solid sleep tonight."

Health context (reference only, do NOT put numbers in the output): {health_data}

Respond in EXACTLY this JSON format and nothing else:
{{"title": "...", "body": "..."}}"""


class NotificationContentGenerator:
    """Generates category-specific notification content via CoachEngine."""

    def __init__(self):
        self.coach = CoachEngine()

    def _generate(self, prompt: str, health_data: dict, user_name: str, fallback_title: str, fallback_body: str) -> dict:
        """Shared generation logic: call AI, parse JSON, fallback on error."""
        try:
            result = self.coach.process_query(
                query=prompt,
                health_data=health_data,
                user_name=user_name,
            )
            content = json.loads(result["response"])
            return {
                "title": content.get("title", fallback_title)[:50],
                "body": content.get("body", fallback_body)[:150],
            }
        except (json.JSONDecodeError, KeyError):
            logger.warning("Failed to parse AI response, using response as body")
            return {"title": fallback_title, "body": result.get("response", fallback_body)[:150]}
        except Exception as e:
            logger.error("AI generation failed: %s", e)
            return {"title": fallback_title, "body": fallback_body}

    def generate_coaching_nudge(self, health_data: dict, user_name: str = "there") -> dict:
        """Cross-domain insight notification. 2-3x per week."""
        # Get relevant knowledge graph connections
        kg = self.coach.knowledge_graph
        connections_text = ""
        relevant = kg.find_relevant_connections(list(health_data.keys()))
        if relevant:
            connections_text = "; ".join(c.to_natural_language() for c in relevant[:3])
        else:
            connections_text = "protein→deep sleep; dinner timing→sleep quality; exercise→next-day recovery"

        data_summary = self._build_data_summary(health_data)

        prompt = COACHING_NUDGE_PROMPT.format(
            shared_rules=SHARED_RULES,
            health_data=data_summary,
            connections=connections_text,
        )

        content = self._generate(
            prompt, health_data, user_name,
            fallback_title="Your coach spotted something",
            fallback_body="A pattern in your health data is worth checking out. Tap to see.",
        )

        return {
            **content,
            "category": "coaching_nudge",
            "apns": {
                "category": "COACHING_NUDGE",
                "thread_id": "coaching-insights",
                "interruption_level": "active",
                "relevance_score": 0.7,
                "collapse_id": f"coaching-nudge-{datetime.utcnow().strftime('%Y-%m-%d')}",
            },
            "data": {
                "deep_link": "meld://coach",
                "notification_type": "coaching_nudge",
            },
        }

    def generate_bedtime_coaching(self, health_data: dict, user_name: str = "there") -> dict:
        """Wind-down reminder timed to the user's sleep window."""
        data_summary = self._build_data_summary(health_data)

        prompt = BEDTIME_COACHING_PROMPT.format(
            shared_rules=SHARED_RULES,
            health_data=data_summary,
        )

        content = self._generate(
            prompt, health_data, user_name,
            fallback_title="Time to wind down",
            fallback_body="Your body will thank you for an early night. Try some deep breathing.",
        )

        return {
            **content,
            "category": "bedtime_coaching",
            "apns": {
                "category": "BEDTIME_COACHING",
                "thread_id": "sleep-coaching",
                "interruption_level": "active",  # NOT time-sensitive — don't break Focus
                "relevance_score": 0.6,
                "collapse_id": f"bedtime-{datetime.utcnow().strftime('%Y-%m-%d')}",
            },
            "data": {
                "deep_link": "meld://dashboard",
                "notification_type": "bedtime_coaching",
            },
        }

    def generate_streak_saver(
        self, streak_count: int, streak_goal: int, user_name: str = "there"
    ) -> dict | None:
        """Streak saver notification. Only fires when streak is at risk.

        Returns None if no streak is at risk (caller should skip).
        Uses loss-aversion framing (Duolingo pattern).
        """
        if streak_count >= streak_goal:
            return None  # Already hit goal, no alert needed

        return {
            "title": "Don't lose your streak",
            "body": f"You're at {streak_count} of {streak_goal} days this week. One more keeps it alive.",
            "category": "streak_saver",
            "apns": {
                "category": "STREAK_SAVER",
                "thread_id": "streak-alerts",
                "interruption_level": "active",
                "relevance_score": 0.8,
                "collapse_id": f"streak-{datetime.utcnow().strftime('%Y-%m-%d')}",
            },
            "data": {
                "deep_link": "meld://dashboard",
                "notification_type": "streak_saver",
            },
        }

    def generate_weekly_review(
        self, health_data_7d: dict, user_name: str = "there"
    ) -> dict:
        """Weekly summary notification. Passive interruption level."""
        week_workout_days = health_data_7d.get("workout_days", 0)
        sleep_trend = health_data_7d.get("sleep_trend", "stable")

        if sleep_trend == "improving" and week_workout_days >= 4:
            body = f"Solid week. Sleep improved and you hit {week_workout_days} workout days. Keep it going."
        elif week_workout_days >= 3:
            body = "Good consistency this week. Your body is responding well. Review inside."
        else:
            body = "Mixed week. Small improvements add up. See your full review."

        return {
            "title": "Your week in review",
            "body": body[:150],
            "category": "weekly_review",
            "apns": {
                "category": "WEEKLY_REVIEW",
                "thread_id": "weekly-review",
                "interruption_level": "passive",  # Low priority — Notification Center only
                "relevance_score": 0.4,
                "collapse_id": f"weekly-{datetime.utcnow().strftime('%Y-%W')}",
            },
            "data": {
                "deep_link": "meld://trends",
                "notification_type": "weekly_review",
            },
        }

    def generate_health_alert(self, health_data: dict, safety_reasons: list[str]) -> dict | None:
        """Health alert for biometric deviation. Time-sensitive.

        Returns None if no concerning data (caller should skip).
        NEVER includes raw metric values in title or body (privacy).
        """
        if not safety_reasons:
            return None

        from app.config import settings
        base_url = "http://localhost:8000" if settings.app_env == "development" else "https://zippy-forgiveness-production-0704.up.railway.app"
        media_url = generate_recovery_badge("low", base_url=base_url)

        return {
            "title": "Your coach flagged something",
            "body": "Some of your health signals are outside your normal range. Take a look when you can.",
            "category": "health_alert",
            "media_url": media_url,
            "apns": {
                "category": "HEALTH_ALERT",
                "thread_id": "health-alerts",
                "interruption_level": "time-sensitive",
                "relevance_score": 1.0,
                "collapse_id": f"health-alert-{datetime.utcnow().strftime('%Y-%m-%d')}",
            },
            "data": {
                "deep_link": "meld://dashboard",
                "notification_type": "health_alert",
                "safety_reasons_count": len(safety_reasons),
            },
        }

    def _build_data_summary(self, health_data: dict) -> str:
        """Build a concise data summary string for prompts."""
        parts = []
        readiness = health_data.get("readiness_score")
        if readiness:
            level = "high" if readiness >= 67 else "moderate" if readiness >= 34 else "low"
            parts.append(f"Recovery: {level}")
        if health_data.get("sleep_efficiency"):
            parts.append(f"Sleep: {health_data['sleep_efficiency']:.0f}%")
        if health_data.get("hrv_average"):
            parts.append(f"HRV: {health_data['hrv_average']:.0f}ms")
        if health_data.get("resting_hr"):
            parts.append(f"RHR: {health_data['resting_hr']:.0f}bpm")
        return ", ".join(parts) or "No data available"


# Singleton
content_generator = NotificationContentGenerator()
