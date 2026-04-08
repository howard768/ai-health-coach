from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db
from app.routers import auth, health, coach, notifications
from app.tasks.scheduler import start_scheduler, stop_scheduler


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

# CORS — allow iOS app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve notification media (recovery badges, etc.)
media_dir = Path(__file__).resolve().parent.parent / "media"
media_dir.mkdir(exist_ok=True)
app.mount("/media", StaticFiles(directory=str(media_dir)), name="media")

# Mount routers
app.include_router(auth.router)
app.include_router(health.router)
app.include_router(coach.router)
app.include_router(notifications.router)


@app.get("/")
async def health_check():
    return {
        "status": "healthy",
        "app": "Meld Health Coach API",
        "version": "0.1.0",
        "environment": settings.app_env,
    }
