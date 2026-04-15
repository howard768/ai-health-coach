"""Phase 4.5 Commit 5 follow-up: synth_drift_job scheduler wiring tests.

Pins that the daily job:

1. Exists as a defined function in the scheduler module.
2. Is registered with ``id="synth_drift"`` and cron ``04:15 UTC`` when
   the scheduler is started.
3. Short-circuits cleanly when the database has no synth rows yet.
4. Swallows exceptions and logs them rather than crashing the
   scheduler (APScheduler running a raising coroutine kills the job
   queue in some configurations; tests pin the defensive catch).

Run: ``cd backend && uv run python -m pytest tests/ml/test_synth_drift_scheduler.py -v``
"""

from __future__ import annotations

import logging
import os

os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-must-be-long-enough-for-hs256-aaaaaaaa")
os.environ.setdefault("ENCRYPTION_KEY", "T0TXLkHFSeZRYGIIejSFVkhQrvRE-bWLkwXSkkdWiKQ=")
os.environ.setdefault("ANTHROPIC_API_KEY", "fake-key-tests-dont-call-anthropic")

from contextlib import asynccontextmanager
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models.health import HealthMetricRecord
from app.tasks import scheduler as scheduler_module
from app.tasks.scheduler import synth_drift_job


# ─────────────────────────────────────────────────────────────────────────
# Shape
# ─────────────────────────────────────────────────────────────────────────


def test_synth_drift_job_is_an_async_function() -> None:
    import inspect

    assert inspect.iscoroutinefunction(synth_drift_job)


def test_synth_drift_job_is_registered_with_expected_id_at_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Walk the source of ``start_scheduler`` to verify the
    registration block names our job with the expected id and minute.

    A full ``start_scheduler()`` call would fire every other job on a
    fresh scheduler instance -- heavy, and APScheduler's cron trigger
    would try to schedule push notifications at real times in test
    context. This AST-style assertion pins the registration without
    starting the scheduler."""
    source = Path(scheduler_module.__file__).read_text(encoding="utf-8")
    assert 'id="synth_drift"' in source
    assert "CronTrigger(hour=4, minute=15)" in source
    assert "synth_drift_job" in source


# ─────────────────────────────────────────────────────────────────────────
# Behavior (dataset_too_small short-circuit)
# ─────────────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def empty_session_factory():
    """In-memory SQLite session factory, empty schema."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_job_short_circuits_when_dataset_too_small(
    empty_session_factory, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Empty DB -> job logs 'dataset too small' and returns cleanly."""

    @asynccontextmanager
    async def fake_async_session():
        async with empty_session_factory() as s:
            yield s

    monkeypatch.setattr(scheduler_module, "async_session", fake_async_session)

    caplog.set_level(logging.INFO, logger="meld.scheduler")
    await synth_drift_job()

    assert any(
        "dataset too small" in rec.getMessage() for rec in caplog.records
    ), "expected a 'dataset too small' log line"


@pytest.mark.asyncio
async def test_job_logs_drift_summary_when_data_present(
    empty_session_factory, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    """Seed real + synth rows, force the Evidently HTML path to no-op,
    verify the done-log fires with the expected summary shape."""
    import numpy as np

    # Seed 60 days x 3 users on each partition with a 3-sd HRV shift.
    async with empty_session_factory() as session:
        rng = np.random.default_rng(11)
        for u in range(3):
            for d in range(60):
                date_s = f"2026-0{(d % 9) + 1}-{(d % 28) + 1:02d}"
                session.add(
                    HealthMetricRecord(
                        user_id=f"u-real-{u}",
                        date=date_s,
                        metric_type="hrv",
                        value=float(rng.normal(50.0, 5.0)),
                        source="oura",
                        is_canonical=True,
                        is_synthetic=False,
                    )
                )
                session.add(
                    HealthMetricRecord(
                        user_id=f"u-synth-{u}",
                        date=date_s,
                        metric_type="hrv",
                        value=float(rng.normal(65.0, 5.0)),
                        source="synth",
                        is_canonical=True,
                        is_synthetic=True,
                    )
                )
        await session.commit()

    @asynccontextmanager
    async def fake_async_session():
        async with empty_session_factory() as s:
            yield s

    monkeypatch.setattr(scheduler_module, "async_session", fake_async_session)

    # Force the Evidently HTML writer to a no-op so the test does not
    # depend on Python version behavior in the evidently dep.
    monkeypatch.setattr(
        "ml.mlops.evidently_reports._try_build_evidently_html",
        lambda *args, **kwargs: None,
    )

    caplog.set_level(logging.INFO, logger="meld.scheduler")
    await synth_drift_job()

    done_lines = [
        rec.getMessage()
        for rec in caplog.records
        if rec.getMessage().startswith("synth_drift_job done")
    ]
    assert done_lines, "expected a 'synth_drift_job done' log line"
    done = done_lines[0]
    assert "ref=180" in done
    assert "cur=180" in done
    assert "hrv" in done  # mentioned in drifted list


# ─────────────────────────────────────────────────────────────────────────
# Error handling (invariant 4)
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_job_swallows_unexpected_exceptions(
    empty_session_factory, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """APScheduler must never see an uncaught exception from our job.
    Patch ``build_synth_drift_report`` to raise; verify the job logs
    and returns without propagating."""

    @asynccontextmanager
    async def fake_async_session():
        async with empty_session_factory() as s:
            yield s

    async def _boom(*args, **kwargs):
        raise RuntimeError("pretend ml.api blew up")

    monkeypatch.setattr(scheduler_module, "async_session", fake_async_session)
    monkeypatch.setattr("ml.api.build_synth_drift_report", _boom)

    caplog.set_level(logging.ERROR, logger="meld.scheduler")
    # Must not raise.
    await synth_drift_job()

    assert any(
        "synth_drift_job unexpected error" in rec.getMessage()
        for rec in caplog.records
    )
