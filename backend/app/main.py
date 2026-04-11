from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import settings
from app.database import init_db
from app.routers import auth, auth_apple, health, coach, notifications, meals, user, peloton_auth, garmin_auth, webhooks
from app.tasks.scheduler import start_scheduler, stop_scheduler


# Rate limiter — keyed by remote IP. Default limits apply to every endpoint
# unless overridden with @limiter.limit("..."). Stricter limits applied to
# auth + AI endpoints to prevent cost-exhaustion attacks (P1-4).
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["120/minute"],  # Generous baseline for normal app usage
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables + start scheduler
    await init_db()
    start_scheduler()
    yield
    # Shutdown: stop scheduler
    stop_scheduler()


app = FastAPI(
    title="Meld Health Coach API",
    description="Backend for Meld — AI-powered health coaching",
    version="0.1.0",
    lifespan=lifespan,
)

# Wire up rate limiter — slowapi attaches `request.app.state.limiter` and
# auto-returns 429 with Retry-After when limits are exceeded.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — restrict to known origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://192.168.86.47:8000",
        "https://zippy-forgiveness-production-0704.up.railway.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve notification media (recovery badges, etc.)
media_dir = Path(__file__).resolve().parent.parent / "media"
media_dir.mkdir(exist_ok=True)
app.mount("/media", StaticFiles(directory=str(media_dir)), name="media")

# Mount routers
app.include_router(auth.router)          # Legacy Oura OAuth callback
app.include_router(auth_apple.router)    # Sign in with Apple + JWT refresh
app.include_router(health.router)
app.include_router(coach.router)
app.include_router(notifications.router)
app.include_router(meals.router)
app.include_router(user.router)
app.include_router(peloton_auth.router)
app.include_router(garmin_auth.router)
app.include_router(webhooks.router)


@app.get("/")
async def health_check():
    """Public root endpoint — no DB ping. Marketing/curiosity check only."""
    return {
        "status": "healthy",
        "app": "Meld Health Coach API",
        "version": "0.1.0",
        "environment": settings.app_env,
    }


@app.get("/healthz")
async def healthz():
    """Liveness probe — process is up. No DB check (cheap, fast)."""
    return {"status": "ok"}


@app.get("/readyz")
async def readyz():
    """Readiness probe — verifies DB connection. Used by Railway/uptime monitors
    to gate traffic. Returns 503 if the DB is unreachable.
    """
    from sqlalchemy import text
    from app.database import async_session
    try:
        async with async_session() as db:
            await db.execute(text("SELECT 1"))
        return {"status": "ready", "db": "ok"}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail=f"Database not ready: {e}")
