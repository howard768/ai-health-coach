"""Phase 4.5 Commit 5: public API wiring for drift reporting.

The rest of backend.app may only import ``ml.api``, so drift
monitoring must be reachable through that surface. This test pins
the delegation contract.

Run: ``cd backend && uv run python -m pytest tests/ml/test_drift_api.py -v``
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-must-be-long-enough-for-hs256-aaaaaaaa")
os.environ.setdefault("ENCRYPTION_KEY", "T0TXLkHFSeZRYGIIejSFVkhQrvRE-bWLkwXSkkdWiKQ=")
os.environ.setdefault("ANTHROPIC_API_KEY", "fake-key-tests-dont-call-anthropic")

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models.health import HealthMetricRecord
from app.models.ml_drift import MLDriftResult  # noqa: F401 -- ensure schema create
from ml.api import (
    DRIFT_KS_THRESHOLD,
    DriftReportSummary,
    build_synth_drift_report,
    persist_drift_results,
)


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_public_entry_returns_drift_report_summary(db: AsyncSession, tmp_path: Path) -> None:
    """Empty-DB path: delegation still works and returns the public
    shape, not the internal DriftReport."""
    report = await build_synth_drift_report(db, output_dir=str(tmp_path))
    assert isinstance(report, DriftReportSummary)
    assert report.dataset_too_small is True
    assert report.html_path is None


@pytest.mark.asyncio
async def test_public_entry_flags_drift_through_delegation(
    db: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sanity: a shifted HRV distribution registers as drift through
    the public surface, not just the internal helper."""
    import numpy as np

    rng = np.random.default_rng(1)
    for u in range(3):
        for d in range(60):
            date_s = f"2026-0{(d % 9) + 1}-{(d % 28) + 1:02d}"
            db.add(
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
            db.add(
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
    await db.flush()

    # Suppress the HTML attempt so this test does not touch evidently.
    monkeypatch.setattr(
        "ml.mlops.evidently_reports._try_build_evidently_html",
        lambda *args, **kwargs: None,
    )

    report = await build_synth_drift_report(db, output_dir=str(tmp_path))
    assert report.dataset_too_small is False
    assert "hrv" in report.drifted_metrics
    assert report.p_values["hrv"] < 0.05
    # New fields populate for the persistence layer.
    assert "hrv" in report.ks_statistics
    assert report.ks_statistics["hrv"] > 0.0
    assert report.sample_sizes["hrv"] == (180, 180)


@pytest.mark.asyncio
async def test_persist_drift_results_writes_one_row_per_metric(
    db: AsyncSession,
) -> None:
    """persist_drift_results inserts one ml_drift_results row per metric
    in summary.ks_statistics, with drifted = (ks_stat > threshold)."""
    from sqlalchemy import select

    summary = DriftReportSummary(
        run_id="test-run-1" + "0" * 20,
        created_at="2026-04-17T12:00:00+00:00",
        html_path=None,
        html_backend="none",
        n_reference_rows=180,
        n_current_rows=180,
        metrics_tested=["hrv", "steps"],
        drifted_metrics=["hrv"],
        p_values={"hrv": 0.001, "steps": 0.9},
        ks_statistics={"hrv": 0.42, "steps": 0.05},
        sample_sizes={"hrv": (180, 180), "steps": (180, 180)},
        dataset_too_small=False,
        threshold=0.05,
    )

    persisted = await persist_drift_results(db, summary)
    assert persisted == 2
    await db.commit()

    result = await db.execute(
        select(MLDriftResult).order_by(MLDriftResult.feature_key)
    )
    rows = list(result.scalars().all())
    assert len(rows) == 2
    by_key = {r.feature_key: r for r in rows}
    # hrv: KS stat 0.42 > 0.15 threshold -> drifted
    assert by_key["hrv"].drifted is True
    assert by_key["hrv"].ks_statistic == pytest.approx(0.42)
    assert by_key["hrv"].threshold == pytest.approx(DRIFT_KS_THRESHOLD)
    assert by_key["hrv"].sample_size_real == 180
    assert by_key["hrv"].sample_size_synth == 180
    # steps: KS stat 0.05 <= 0.15 threshold -> NOT drifted
    assert by_key["steps"].drifted is False
    # Both rows share the run_id from the summary.
    assert {r.synth_run_id for r in rows} == {summary.run_id}


@pytest.mark.asyncio
async def test_persist_drift_results_skips_dataset_too_small(
    db: AsyncSession,
) -> None:
    """When the drift run was skipped (too small), nothing is written."""
    from sqlalchemy import func, select

    summary = DriftReportSummary(
        run_id="skip-run",
        created_at="2026-04-17T12:00:00+00:00",
        html_path=None,
        html_backend="none",
        n_reference_rows=0,
        n_current_rows=0,
        dataset_too_small=True,
        threshold=0.05,
    )
    persisted = await persist_drift_results(db, summary)
    assert persisted == 0
    count = await db.execute(select(func.count()).select_from(MLDriftResult))
    assert count.scalar() == 0
