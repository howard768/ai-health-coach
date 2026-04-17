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
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db

logger = logging.getLogger("meld.ops")

router = APIRouter(prefix="/ops", tags=["ops"])


# Per-table freshness column map. Each ML table uses a different timestamp
# column (computed_at, generated_at, etc.). ml_synth_runs.created_at is a
# String ISO-8601 timestamp, not a DateTime, so the MAX() result comes back
# as a str and is returned verbatim. Everything else is a DateTime.
_FRESHNESS_SOURCES: dict[str, tuple[str, str]] = {
    "ml_features_latest": ("ml_features", "computed_at"),
    "ml_baselines_latest": ("ml_baselines", "computed_at"),
    "ml_insights_latest": ("ml_insights", "generated_at"),
    "ml_synth_runs_latest": ("ml_synth_runs", "created_at"),
    "user_correlations_latest": ("user_correlations", "discovered_at"),
    "notification_records_latest": ("notification_records", "sent_at"),
}


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
    sentry_enabled: bool
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
    Per-table column map lives in ``_FRESHNESS_SOURCES``; each table has its
    own timestamp column name (``computed_at``, ``generated_at`` etc.).
    Tables may not exist in all environments, so each query is try/excepted
    independently so one missing table does not zero out the rest.
    """
    results: dict[str, str | None] = {}
    for key, (table, column) in _FRESHNESS_SOURCES.items():
        try:
            row = await db.execute(
                text(f"SELECT MAX({column}) FROM {table}")  # noqa: S608
            )
            val = row.scalar()
            if val is None:
                results[key] = None
            elif isinstance(val, datetime):
                results[key] = val.isoformat()
            else:
                # Two sources of strings here: ml_synth_runs.created_at is a
                # String column already in ISO-8601 with T separator. SQLite's
                # raw-SQL path also returns DateTime columns as text with a
                # space separator ("YYYY-MM-DD HH:MM:SS.ffffff"). Normalize
                # to T so downstream parsers get a consistent ISO-8601 string.
                s = str(val)
                if len(s) >= 11 and s[10] == " ":
                    s = s[:10] + "T" + s[11:]
                results[key] = s
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
        sentry_enabled=bool(settings.sentry_dsn),
        jobs=jobs,
        pipeline_freshness=pipeline,
        db_ok=db_ok,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
