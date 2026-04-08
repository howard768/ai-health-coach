from fastapi import APIRouter
from pydantic import BaseModel

from app.services.coach_engine import CoachEngine

router = APIRouter(prefix="/api/coach", tags=["coach"])

# Singleton engine (will be dependency-injected in production)
engine = CoachEngine()

# Health context with numeric values for evidence-bound coaching
# In production, pulled from DB (real Oura data)
MOCK_HEALTH_CONTEXT = {
    "sleep_efficiency": 91,
    "sleep_duration_hours": 7.2,
    "deep_sleep_minutes": 82,
    "hrv_average": 68,
    "baseline_hrv": 58,
    "resting_hr": 58,
    "baseline_rhr": 62,
    "readiness_score": 82,
    "training_days_this_week": 5,
    "training_target": 5,
}


class ChatRequest(BaseModel):
    message: str
    history: list[dict] | None = None


class ChatResponse(BaseModel):
    role: str
    content: str
    routing: dict | None = None
    safety: dict | None = None
    model_used: str | None = None


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """AI coach — full research-informed pipeline.

    Pipeline:
    1. Safety check (ILION: deterministic pre-execution gates)
    2. Deliberation routing (DOVA: rules before AI, 40-60% cost savings)
    3. Evidence-bound response (EviBound: every claim cites data)
    4. Explainable routing logged (Topaz: why this model was chosen)
    """
    result = engine.process_query(
        query=request.message,
        health_data=MOCK_HEALTH_CONTEXT,
        user_goals=["Lose weight", "Build muscle"],
        history=request.history,
    )

    return ChatResponse(
        role="coach",
        content=result["response"],
        routing=result.get("routing"),
        safety=result.get("safety"),
        model_used=result.get("model_used"),
    )


@router.post("/insight")
async def generate_insight():
    """Generate daily dashboard insight via the full engine pipeline."""
    result = engine.generate_daily_insight(
        health_data=MOCK_HEALTH_CONTEXT,
        user_goals=["Lose weight", "Build muscle"],
    )
    return result
