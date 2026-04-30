from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.core.encryption import verify_encryption_configured
from app.routers import auth, auth_apple, health, coach, notifications, meals, user, peloton_auth, garmin_auth, webhooks, waitlist, mascot, insights, privacy, experiments, ops, ml_ops
from app.tasks.scheduler import start_scheduler, stop_scheduler


def _real_remote_address(request: Request) -> str:
    """Extract the real client IP, preferring trusted forwarded headers.

    The default `slowapi.util.get_remote_address` returns
    `request.client.host`, which on Railway behind Cloudflare is always
    the CF edge IP. That collapses every rate-limit bucket to one shared
    counter — any single user can exhaust the limit for everyone.

    Trust order:
      1. `cf-connecting-ip` (Cloudflare-injected, only present when traffic
         actually transited Cloudflare; CF strips any client-supplied value)
      2. First entry of `x-forwarded-for` (Railway's edge sets this; behaves
         like an XFF chain so we take the leftmost = original client)
      3. `request.client.host` (raw socket peer, last resort)

    The 2026-04-29 audit (BLOCKER, backend_app_audit.md) flagged this as
    rate-limit-bypass-via-shared-bucket. Fixing here applies to every
    endpoint that uses the global limiter.
    """
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.strip()
    xff = request.headers.get("x-forwarded-for")
    if xff:
        first = xff.split(",", 1)[0].strip()
        if first:
            return first
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


# Rate limiter — keyed by real client IP via _real_remote_address (above).
# Default limits apply to every endpoint unless overridden with
# @limiter.limit("..."). Stricter limits applied to auth + AI endpoints to
# prevent cost-exhaustion attacks (P1-4).
limiter = Limiter(
    key_func=_real_remote_address,
    default_limits=["120/minute"],  # Generous baseline for normal app usage
)


def _init_sentry():
    """Initialize Sentry if a DSN is configured. No-op otherwise."""
    if not settings.sentry_dsn:
        return
    import sentry_sdk
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        traces_sample_rate=0.1,  # 10% of requests traced (cost control)
        profiles_sample_rate=0.1,
        environment=settings.app_env,
        send_default_pii=False,  # Never send PHI/PII to Sentry
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Sentry, encryption check, scheduler. Migrations are NOT run
    # here — Railway's preDeployCommand owns alembic upgrade head (see
    # backend/railway.toml).
    # See ~/.claude/projects/.../memory/feedback_alembic_in_lifespan.md for
    # why: the 5-minute Railway healthcheck window is hostile to migrations,
    # a hung migration here brings the whole app down, and a failed
    # preDeployCommand keeps the previous SUCCESS deploy serving instead.
    _init_sentry()
    # Fail-closed in prod if ENCRYPTION_KEY is missing or unparseable. Better
    # to fail healthcheck and roll back than silently write plaintext PHI for
    # hours waiting for the first OAuth refresh to surface the misconfig.
    verify_encryption_configured()
    start_scheduler()
    yield
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

# CORS — restrict to known origins. P3-3: read public URL from settings
# so changing the deploy URL is one config change, not a grep job.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.local_base_url,
        "http://192.168.86.47:8000",
        settings.public_base_url,
        # Marketing site (heymeld.com) — the Astro app posts to /api/waitlist/subscribe
        "https://heymeld.com",
        "https://www.heymeld.com",
        # Cloudflare Pages preview deployments
        "https://heymeld.pages.dev",
        # Local Astro dev server
        "http://localhost:4321",
        "http://localhost:4322",
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
app.include_router(waitlist.router)    # Public waitlist signup (heymeld.com)
app.include_router(mascot.router)      # Mascot accessory wardrobe
app.include_router(insights.router)    # Signal Engine Phase 4: daily ranked insight + feedback
app.include_router(privacy.router)     # Phase 8: cohort opt-in/opt-out + deletion
app.include_router(experiments.router) # Phase 9: n-of-1 experiment CRUD + APTE results
app.include_router(ops.router)         # Ops status for autonomous monitoring loops
app.include_router(ml_ops.router)      # Read-only ML ops endpoints for Phase 5 monitors


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
    """Readiness probe — verifies DB *and schema* are healthy.

    Querying alembic_version (rather than SELECT 1) ensures the schema
    chain has run. SELECT 1 succeeds against an empty Postgres, which
    masked total schema loss for 10 days during the 2026-04-29 incident.
    See ~/.claude/projects/.../memory/feedback_db_ok_must_query_real_table.md.
    """
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError, DBAPIError
    from app.database import async_session
    try:
        async with async_session() as db:
            await db.execute(text("SELECT 1 FROM alembic_version LIMIT 1"))
        return {"status": "ready", "db": "ok"}
    except (SQLAlchemyError, DBAPIError, OSError) as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail=f"Database not ready: {e}")
