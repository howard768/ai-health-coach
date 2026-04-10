from datetime import datetime
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.database import get_db
from app.models.chat import Conversation, ChatMessageRecord
from app.services.coach_engine import CoachEngine
from app.services.health_data import get_latest_health_data

router = APIRouter(prefix="/api/coach", tags=["coach"])

engine = CoachEngine()


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    role: str
    content: str
    message_id: int | None = None
    routing: dict | None = None
    safety: dict | None = None
    model_used: str | None = None


class HistoryMessage(BaseModel):
    id: int
    role: str
    content: str
    model_used: str | None = None
    routing_tier: str | None = None
    created_at: str


class HistoryResponse(BaseModel):
    messages: list[HistoryMessage]
    conversation_id: int


# ============================================================
# CHAT — Send message, persist both user + coach messages
# ============================================================

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    """Send a message, get AI response, persist both to DB."""

    user_id = "default"  # TODO: from auth

    # Get or create conversation
    conv = await _get_or_create_conversation(db, user_id)

    # Load recent history from DB for context (last 20 messages)
    history_records = await _get_recent_messages(db, conv.id, limit=20)
    # Map DB roles to Claude API roles (coach → assistant)
    history = [{"role": "assistant" if m.role == "coach" else "user", "content": m.content} for m in history_records]

    # Save user message
    user_msg = ChatMessageRecord(
        conversation_id=conv.id,
        user_id=user_id,
        role="user",
        content=request.message,
    )
    db.add(user_msg)
    await db.flush()

    # Load reconciled health data (multi-source: Oura + Apple Health + Garmin)
    health_data = await get_latest_health_data(db, user_id)

    # Process through coach engine (with conversation history)
    # Wrap in to_thread because process_query() calls synchronous Anthropic SDK
    import asyncio
    result = await asyncio.to_thread(
        engine.process_query,
        request.message,
        health_data,
        "Brock",
        ["Lose weight", "Build muscle"],
        history,
    )

    # Strip markdown formatting — our chat UI renders plain text
    import re
    clean_response = result["response"]
    clean_response = re.sub(r'\*\*(.+?)\*\*', r'\1', clean_response)  # **bold** → bold
    clean_response = re.sub(r'\*(.+?)\*', r'\1', clean_response)  # *italic* → italic
    clean_response = re.sub(r'^#{1,3}\s+', '', clean_response, flags=re.MULTILINE)  # ## headers → plain
    clean_response = re.sub(r'^- ', '• ', clean_response, flags=re.MULTILINE)  # - bullets → •
    result["response"] = clean_response

    # Save coach response
    coach_msg = ChatMessageRecord(
        conversation_id=conv.id,
        user_id=user_id,
        role="coach",
        content=clean_response,
        routing_tier=result.get("routing", {}).get("tier"),
        routing_reason=result.get("routing", {}).get("reason"),
        model_used=result.get("model_used"),
        safety_flagged=result.get("safety", {}).get("is_concerning", False),
    )
    db.add(coach_msg)
    await db.commit()
    await db.refresh(coach_msg)

    # Update conversation timestamp
    conv.updated_at = datetime.utcnow()
    await db.commit()

    return ChatResponse(
        role="coach",
        content=result["response"],
        message_id=coach_msg.id,
        routing=result.get("routing"),
        safety=result.get("safety"),
        model_used=result.get("model_used"),
    )


# ============================================================
# HISTORY — Retrieve persisted conversation
# ============================================================

@router.get("/history", response_model=HistoryResponse)
async def get_history(db: AsyncSession = Depends(get_db)):
    """Retrieve full conversation history for the current user."""

    user_id = "default"

    conv = await _get_or_create_conversation(db, user_id)
    records = await _get_recent_messages(db, conv.id, limit=100)

    messages = [
        HistoryMessage(
            id=m.id,
            role=m.role,
            content=m.content,
            model_used=m.model_used,
            routing_tier=m.routing_tier,
            created_at=m.created_at.isoformat(),
        )
        for m in records
    ]

    return HistoryResponse(messages=messages, conversation_id=conv.id)


# ============================================================
# INSIGHT — Daily dashboard insight
# ============================================================

@router.post("/insight")
async def generate_insight(db: AsyncSession = Depends(get_db)):
    """Generate daily dashboard insight via the engine pipeline."""
    health_data = await get_latest_health_data(db, "default")
    result = engine.generate_daily_insight(
        health_data=health_data,
        user_goals=["Lose weight", "Build muscle"],
    )
    return result


# ============================================================
# HELPERS
# ============================================================

async def _get_or_create_conversation(db: AsyncSession, user_id: str) -> Conversation:
    """Get the user's active conversation or create one."""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(desc(Conversation.updated_at))
        .limit(1)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        conv = Conversation(user_id=user_id)
        db.add(conv)
        await db.flush()
    return conv


async def _get_recent_messages(db: AsyncSession, conversation_id: int, limit: int = 20) -> list[ChatMessageRecord]:
    """Get recent messages for a conversation, oldest first."""
    result = await db.execute(
        select(ChatMessageRecord)
        .where(ChatMessageRecord.conversation_id == conversation_id)
        .order_by(desc(ChatMessageRecord.created_at))
        .limit(limit)
    )
    messages = list(result.scalars().all())
    messages.reverse()  # Return oldest first for context
    return messages
