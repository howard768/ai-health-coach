from fastapi import APIRouter
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.services.claude import ClaudeClient

router = APIRouter(prefix="/api/coach", tags=["coach"])


class ChatRequest(BaseModel):
    message: str
    history: list[dict] | None = None


class ChatResponse(BaseModel):
    role: str
    content: str


# Mock health context (will come from DB in production)
MOCK_HEALTH_CONTEXT = {
    "sleep_efficiency": "91%",
    "sleep_duration": "7h 12m",
    "hrv": "68ms (+14% vs baseline)",
    "resting_hr": "58 bpm (stable)",
    "readiness": "High",
    "training": "5/7 days this week",
    "goals": "Lose weight, Build muscle",
    "weight": "185 lbs, target 170 lbs",
}


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Send a message to the AI coach and get a response."""
    client = ClaudeClient()
    response_text = client.chat(
        message=request.message,
        health_context=MOCK_HEALTH_CONTEXT,
        history=request.history,
    )
    return ChatResponse(role="coach", content=response_text)


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """Stream a response from the AI coach via Server-Sent Events."""

    async def generate():
        client = ClaudeClient()
        with client.stream_chat(
            message=request.message,
            health_context=MOCK_HEALTH_CONTEXT,
            history=request.history,
        ) as stream:
            for text in stream.text_stream:
                yield {"data": text}

    return EventSourceResponse(generate())
