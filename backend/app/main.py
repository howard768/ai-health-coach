from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routers import auth, health, coach


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables
    await init_db()
    yield
    # Shutdown: cleanup


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

# Mount routers
app.include_router(auth.router)
app.include_router(health.router)
app.include_router(coach.router)


@app.get("/")
async def health_check():
    return {
        "status": "healthy",
        "app": "Meld Health Coach API",
        "version": "0.1.0",
        "environment": settings.app_env,
    }
