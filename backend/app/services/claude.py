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
            model="claude-sonnet-4-20250514",
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

    def chat(self, message: str, health_context: dict, history: list[dict] | None = None) -> str:
        system_prompt = f"""You are a personal health coach. You have access to the user's health data and provide personalized advice.

Current health data:
{health_context}

Rules:
- Write at a 4th grade reading level. Short sentences. Simple words.
- Be warm, supportive, and specific. Reference their actual data.
- When discussing workouts, give specific sets/reps/weight recommendations.
- When discussing food, give practical meal suggestions.
- When asked about sleep or recovery, explain what their numbers mean.
- Never give medical advice."""

        messages = []
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": message})

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            system=system_prompt,
            messages=messages,
        )
        return response.content[0].text

    def stream_chat(self, message: str, health_context: dict, history: list[dict] | None = None):
        system_prompt = f"""You are a personal health coach. You have access to the user's health data.

Current health data:
{health_context}

Rules:
- Write at a 4th grade reading level. Short sentences. Simple words.
- Be warm, supportive, and specific. Reference their actual data.
- Never give medical advice."""

        messages = []
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": message})

        return self.client.messages.stream(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            system=system_prompt,
            messages=messages,
        )
