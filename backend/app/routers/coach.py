import time
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.api.deps import CurrentUser
from app.database import get_db
from app.models.chat import Conversation, ChatMessageRecord
from app.models.user import User
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
async def chat(
    request: ChatRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Send a message, get AI response, persist both to DB."""

    user_id = current_user.apple_user_id

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

    # Load user profile for personalized name + goals
    user_name, user_goals = await _load_user_context(db, user_id)

    # Process through coach engine (with conversation history)
    # Wrap in to_thread because process_query() calls synchronous Anthropic SDK
    import asyncio
    start_time = time.monotonic()
    result = await asyncio.to_thread(
        engine.process_query,
        request.message,
        health_data,
        user_name,
        user_goals,
        history,
    )
    latency_ms = int((time.monotonic() - start_time) * 1000)

    # Strip markdown formatting — our chat UI renders plain text
    import re
    clean_response = result["response"]
    clean_response = re.sub(r'\*\*(.+?)\*\*', r'\1', clean_response)  # **bold** → bold
    clean_response = re.sub(r'\*(.+?)\*', r'\1', clean_response)  # *italic* → italic
    clean_response = re.sub(r'^#{1,3}\s+', '', clean_response, flags=re.MULTILINE)  # ## headers → plain
    clean_response = re.sub(r'^- ', '• ', clean_response, flags=re.MULTILINE)  # - bullets → •
    result["response"] = clean_response

    # Serialize health context for replay (offline eval)
    import json
    health_context_str = json.dumps(health_data) if health_data else None

    # Save coach response with production monitoring fields
    coach_msg = ChatMessageRecord(
        conversation_id=conv.id,
        user_id=user_id,
        role="coach",
        content=clean_response,
        routing_tier=result.get("routing", {}).get("tier"),
        routing_reason=result.get("routing", {}).get("reason"),
        model_used=result.get("model_used"),
        safety_flagged=result.get("safety", {}).get("is_concerning", False),
        latency_ms=latency_ms,
        input_tokens=result.get("tokens", {}).get("input"),
        output_tokens=result.get("tokens", {}).get("output"),
        health_context=health_context_str,
        prompt_version="v1",  # Increment for A/B tests
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
# FEEDBACK — Thumbs up/down on coach responses
# ============================================================

class FeedbackRequest(BaseModel):
    message_id: int
    feedback: str  # "up" or "down"


@router.post("/feedback")
async def submit_feedback(
    request: FeedbackRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Record thumbs up/down on a coach message owned by the caller."""
    if request.feedback not in ("up", "down"):
        raise HTTPException(status_code=400, detail="feedback must be 'up' or 'down'")

    result = await db.execute(
        select(ChatMessageRecord).where(
            ChatMessageRecord.id == request.message_id,
            ChatMessageRecord.role == "coach",
            ChatMessageRecord.user_id == current_user.apple_user_id,
        )
    )
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="message not found")

    msg.feedback = request.feedback
    msg.feedback_at = datetime.utcnow()
    await db.commit()

    return {"status": "ok", "message_id": request.message_id, "feedback": request.feedback}


# ============================================================
# HISTORY — Retrieve persisted conversation
# ============================================================

@router.get("/history", response_model=HistoryResponse)
async def get_history(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve full conversation history for the current user."""

    user_id = current_user.apple_user_id

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
async def generate_insight(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Generate daily dashboard insight via the engine pipeline."""
    import asyncio
    user_id = current_user.apple_user_id
    health_data = await get_latest_health_data(db, user_id)
    _, user_goals = await _load_user_context(db, user_id)
    # generate_daily_insight calls the sync Anthropic SDK — must offload
    result = await asyncio.to_thread(
        engine.generate_daily_insight,
        health_data,
        user_goals,
    )
    return result


# ============================================================
# ANALYTICS — Production monitoring dashboard
# ============================================================

@router.get("/analytics")
async def get_analytics(
    current_user: CurrentUser,
    days: int = 7,
    db: AsyncSession = Depends(get_db),
):
    """Production monitoring: feedback rates, latency, model usage, safety flags.

    Scoped to the current user's own coach messages.
    """
    from datetime import timedelta
    cutoff = datetime.utcnow() - timedelta(days=days)

    # Only the current user's coach messages in the window
    result = await db.execute(
        select(ChatMessageRecord).where(
            ChatMessageRecord.role == "coach",
            ChatMessageRecord.user_id == current_user.apple_user_id,
            ChatMessageRecord.created_at >= cutoff,
        )
    )
    messages = list(result.scalars().all())

    if not messages:
        return {"period_days": days, "total_responses": 0}

    thumbs_up = sum(1 for m in messages if m.feedback == "up")
    thumbs_down = sum(1 for m in messages if m.feedback == "down")
    no_feedback = sum(1 for m in messages if m.feedback is None)
    safety_flagged = sum(1 for m in messages if m.safety_flagged)

    latencies = [m.latency_ms for m in messages if m.latency_ms]
    avg_latency = round(sum(latencies) / len(latencies)) if latencies else None
    # Nearest-rank p95 — clamp index to valid range so it works for any n >= 1
    if latencies:
        sorted_latencies = sorted(latencies)
        import math
        p95_index = max(0, min(len(sorted_latencies) - 1, math.ceil(0.95 * len(sorted_latencies)) - 1))
        p95_latency = sorted_latencies[p95_index]
    else:
        p95_latency = None

    tokens_in = [m.input_tokens for m in messages if m.input_tokens]
    tokens_out = [m.output_tokens for m in messages if m.output_tokens]

    # Model usage breakdown
    model_counts = {}
    for m in messages:
        key = m.model_used or "rules"
        model_counts[key] = model_counts.get(key, 0) + 1

    # Routing tier breakdown
    tier_counts = {}
    for m in messages:
        key = m.routing_tier or "unknown"
        tier_counts[key] = tier_counts.get(key, 0) + 1

    # Prompt version breakdown (for A/B testing)
    version_feedback = {}
    for m in messages:
        ver = m.prompt_version or "unknown"
        if ver not in version_feedback:
            version_feedback[ver] = {"up": 0, "down": 0, "none": 0, "total": 0}
        version_feedback[ver]["total"] += 1
        if m.feedback == "up":
            version_feedback[ver]["up"] += 1
        elif m.feedback == "down":
            version_feedback[ver]["down"] += 1
        else:
            version_feedback[ver]["none"] += 1

    return {
        "period_days": days,
        "total_responses": len(messages),
        "feedback": {
            "thumbs_up": thumbs_up,
            "thumbs_down": thumbs_down,
            "no_feedback": no_feedback,
            "satisfaction_rate": round(thumbs_up / max(thumbs_up + thumbs_down, 1) * 100, 1),
        },
        "safety": {
            "flagged_count": safety_flagged,
            "flagged_rate": round(safety_flagged / len(messages) * 100, 1),
        },
        "latency": {
            "avg_ms": avg_latency,
            "p95_ms": p95_latency,
        },
        "tokens": {
            "avg_input": round(sum(tokens_in) / len(tokens_in)) if tokens_in else None,
            "avg_output": round(sum(tokens_out) / len(tokens_out)) if tokens_out else None,
            "total_input": sum(tokens_in),
            "total_output": sum(tokens_out),
        },
        "model_usage": model_counts,
        "routing_tiers": tier_counts,
        "prompt_versions": version_feedback,
    }


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


async def _load_user_context(db: AsyncSession, user_id: str) -> tuple[str, list[str]]:
    """Load the user's first name and goals from the profile.

    Falls back to sensible defaults if no profile exists (e.g. after DB reset).
    """
    import json
    result = await db.execute(select(User).where(User.apple_user_id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        return "there", []  # Neutral greeting, no assumed goals

    first_name = (user.name.split()[0] if user.name else "there")

    goals: list[str] = []
    if user.goals:
        try:
            parsed = json.loads(user.goals) if isinstance(user.goals, str) else user.goals
            if isinstance(parsed, list):
                goals = [str(g) for g in parsed]
        except (json.JSONDecodeError, TypeError):
            pass

    return first_name, goals


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
