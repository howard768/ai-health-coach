import anthropic
from app.config import settings


class ClaudeClient:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def generate_insight(self, health_data: dict, user_goals: list[str] | None = None) -> str:
        goals_text = ", ".join(user_goals) if user_goals else "general wellness"

        system_prompt = f"""You are a personal health coach for a user. You have access to their health data and provide evidence-based advice on sleep, recovery, exercise, and nutrition.

The user's goals: {goals_text}

Rules:
- Write at a 4th grade reading level. Short sentences. Simple words.
- Be warm but direct. Tell them what their data means and what to do.
- Reference specific numbers from their data.
- Keep it to 2-3 sentences max for daily insights.
- Never give medical advice. You are a wellness coach, not a doctor."""

        response = self.client.messages.create(
            model=settings.anthropic_model_sonnet,
            max_tokens=200,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": f"Generate a brief daily coaching insight based on this health data:\n{health_data}",
                }
            ],
        )
        return response.content[0].text

    # NOTE: chat() and stream_chat() were here but unused. The real coach
    # pipeline lives in CoachEngine.process_query() which has safety gates,
    # routing, and proper auth. Removed in P2-8 cleanup.
