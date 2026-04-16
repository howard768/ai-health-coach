"""Ops status endpoint for autonomous monitoring loops.

Returns structured JSON aggregating scheduler job metadata, ML pipeline
freshness, and deploy info. Used by Claude Code scheduled tasks to decide
whether to create Linear issues.

Public endpoint (no auth) -- returns operational metadata only, never user
data or PHI. Rate limited to prevent abuse.
"""

import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

logger = logging.getLogger("meld.ops")

router = APIRouter(prefix="/ops", tags=["ops"])


# -- Response models --


class JobStatus(BaseModel):
    id: str
    name: str
    next_run: str | None
    pending: bool


class PipelineFreshness(BaseModel):
    ml_features_latest: str | None
    ml_baselines_latest: str | None
    ml_insights_latest: str | None
    ml_synth_runs_latest: str | None
    user_correlations_latest: str | None
    notification_records_latest: str | None


class OpsStatusResponse(BaseModel):
    status: str
    deploy_sha: str | None
    uptime_env: str
    scheduler_running: bool
    jobs: list[JobStatus]
    pipeline_freshness: PipelineFreshness
    db_ok: bool
    timestamp: str


# -- Helpers --


def _get_scheduler_jobs() -> tuple[bool, list[JobStatus]]:
    """Read APScheduler job list without importing heavy deps."""
    try:
        from app.tasks.scheduler import scheduler

        running = scheduler.running
        jobs = []
        for job in scheduler.get_jobs():
            next_run = None
            if job.next_run_time:
                next_run = job.next_run_time.isoformat()
            jobs.append(
                JobStatus(
                    id=job.id,
                    name=job.name,
                    next_run=next_run,
                    pending=job.pending,
                )
            )
        return running, jobs
    except Exception:
        return False, []


async def _get_pipeline_freshness(db: AsyncSession) -> PipelineFreshness:
    """Query latest timestamps from ML and notification tables.

    Uses raw SQL to avoid importing model classes (keeps cold-boot clean).
    Tables may not exist in all environments, so each query is try/excepted.
    """
    results: dict[str, str | None] = {}
    tables = {
        "ml_features_latest": "ml_features",
        "ml_baselines_latest": "ml_baselines",
        "ml_insights_latest": "ml_insights",
        "ml_synth_runs_latest": "ml_synth_runs",
        "user_correlations_latest": "user_correlations",
        "notification_records_latest": "notification_records",
    }
    for key, table in tables.items():
        try:
            row = await db.execute(
                text(f"SELECT MAX(updated_at) FROM {table}")  # noqa: S608
            )
            val = row.scalar()
            results[key] = val.isoformat() if val else None
        except Exception:
            results[key] = None

    return PipelineFreshness(**results)


# -- Endpoint --


@router.get("/status", response_model=OpsStatusResponse)
async def ops_status(db: AsyncSession = Depends(get_db)) -> OpsStatusResponse:
    """Aggregated ops status for autonomous monitoring agents.

    Returns scheduler job list, ML pipeline freshness timestamps,
    and deploy metadata. No auth required (no user data exposed).
    """
    scheduler_running, jobs = _get_scheduler_jobs()

    pipeline = await _get_pipeline_freshness(db)

    # DB connectivity (same check as /readyz but non-throwing)
    db_ok = True
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    return OpsStatusResponse(
        status="ok" if db_ok and scheduler_running else "degraded",
        deploy_sha=os.environ.get("RAILWAY_GIT_COMMIT_SHA"),
        uptime_env=os.environ.get("APP_ENV", "development"),
        scheduler_running=scheduler_running,
        jobs=jobs,
        pipeline_freshness=pipeline,
        db_ok=db_ok,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
