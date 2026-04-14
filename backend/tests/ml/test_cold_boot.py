"""Cold-boot invariant: ``from app.main import app`` must not pull heavy ML deps.

The Signal Engine plan budgets FastAPI cold boot at < 4 seconds on Railway.
Heavy deps like pandas, scipy, statsmodels, xgboost, prophet, dowhy, econml,
shap, mlflow, evidently, nannyml, coremltools add 2-4 seconds each to import.
If any of them is imported at module load on the main app path, the budget is
blown and Railway healthchecks start failing under load.

This test loads the main app in a subprocess with ``-X importtime`` and asserts
that none of the forbidden module names appear in the trace output. A
subprocess is used so the parent pytest process's already-cached imports do not
mask a violation.

Run: ``cd backend && uv run python -m pytest tests/ml/test_cold_boot.py -v``
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[2]

# Modules whose top-level import is NOT allowed on the main FastAPI cold boot
# path. All of these must be lazy-imported inside backend.ml.api function
# bodies only.
FORBIDDEN_ON_COLD_BOOT = {
    "pandas",
    "numpy",
    "scipy",
    "statsmodels",
    "sklearn",
    "xgboost",
    "prophet",
    "ruptures",
    "pycatch22",
    "shap",
    "hdbscan",
    "mlflow",
    "evidently",
    "nannyml",
    "dowhy",
    "econml",
    "coremltools",
}

# The entry point the cold-boot probe simulates. This is what uvicorn runs.
ENTRY_POINT_SCRIPT = "from app.main import app\n"


def _env_for_subprocess() -> dict[str, str]:
    """Env that lets ``from app.main import app`` succeed without real secrets.

    The main app reads a bunch of required secrets at module load via
    pydantic-settings. Give it dummy values so the import succeeds; we are not
    actually serving traffic, just measuring the import tree.
    """
    env = os.environ.copy()
    env.setdefault("JWT_SECRET_KEY", "cold-boot-test-secret-not-real")
    env.setdefault("ENCRYPTION_KEY", "T0TXLkHFSeZRYGIIejSFVkhQrvRE-bWLkwXSkkdWiKQ=")
    env.setdefault("ANTHROPIC_API_KEY", "cold-boot-fake-key")
    # SQLite fallback used by the test settings.
    env.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    return env


def _run_importtime() -> str:
    """Run ``python -X importtime -c 'from app.main import app'`` and return stderr.

    The ``-X importtime`` flag emits one line per imported module, with fields
    ``self_us | cumulative | import path``. We parse the ``import path``
    column to check forbidden names.
    """
    result = subprocess.run(
        [sys.executable, "-X", "importtime", "-c", ENTRY_POINT_SCRIPT],
        capture_output=True,
        text=True,
        cwd=str(BACKEND_ROOT),
        env=_env_for_subprocess(),
        timeout=60,
    )
    if result.returncode != 0:
        pytest.fail(
            "Subprocess could not import the main app. This may mean a "
            "required env variable is missing, or that the app itself has "
            "a real import error.\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
    return result.stderr


def _parse_imported_modules(importtime_stderr: str) -> list[str]:
    """Extract the set of imported module names from ``-X importtime`` output.

    Lines look like::

        import time:       123 |        456 | foo.bar.baz

    We grab everything after the second ``|`` and strip leading whitespace +
    the Python-printed tree prefix (``|`` characters and spaces).
    """
    modules: list[str] = []
    for line in importtime_stderr.splitlines():
        if "|" not in line:
            continue
        parts = line.split("|", 2)
        if len(parts) < 3:
            continue
        raw = parts[2].strip()
        # The third column is indented with spaces to show the import depth.
        # Normalize to just the module name.
        mod = raw.lstrip(" |")
        if mod:
            modules.append(mod)
    return modules


def test_main_app_cold_boot_does_not_import_ml_heavyweights() -> None:
    """Load the main app in a clean subprocess. No forbidden modules may appear.

    This is the backstop that catches accidental top-level imports of ML deps.
    If this test fails, someone added e.g. ``import pandas`` inside
    ``backend/app/services/...`` or ``backend/ml/api.py`` at module level.
    Move the import inside the function body that actually needs it.
    """
    stderr = _run_importtime()
    imported = _parse_imported_modules(stderr)

    offenders: set[str] = set()
    for mod in imported:
        # Match the root module only (e.g. 'pandas.core.frame' -> 'pandas').
        root = mod.split(".", 1)[0]
        if root in FORBIDDEN_ON_COLD_BOOT:
            offenders.add(root)

    assert not offenders, (
        "Heavy ML deps were imported during cold boot of the FastAPI main app. "
        "This breaks the < 4s Railway boot budget.\n\n"
        f"Offenders: {sorted(offenders)}\n\n"
        "Fix: move the offending import inside the function body that needs "
        "it, never at module top level. See backend/ml/api.py for the pattern."
    )


def test_ml_api_import_is_lightweight() -> None:
    """Importing ``ml.api`` itself must not pull in heavy deps either.

    ``ml.api`` is allowed to be imported from app code. If simply importing
    that module triggered a pandas/scipy/etc load, the whole point of the
    lazy-import discipline is defeated.
    """
    # Tests run with cwd=backend, so the import path is `ml.api`, not
    # `backend.ml.api`. Same convention as `from app.X import ...` in the
    # rest of the test suite.
    script = "import ml.api as api; _ = api\n"
    result = subprocess.run(
        [sys.executable, "-X", "importtime", "-c", script],
        capture_output=True,
        text=True,
        cwd=str(BACKEND_ROOT),
        env=_env_for_subprocess(),
        timeout=30,
    )
    if result.returncode != 0:
        pytest.fail(
            f"Could not import backend.ml.api.\nstdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    imported = _parse_imported_modules(result.stderr)
    offenders = {m.split(".", 1)[0] for m in imported} & FORBIDDEN_ON_COLD_BOOT
    assert not offenders, (
        "Importing backend.ml.api triggered heavy ML deps at module load.\n"
        f"Offenders: {sorted(offenders)}\n\n"
        "Fix: keep all heavy imports inside function bodies. Use TYPE_CHECKING "
        "for type-only imports if you need them for annotations."
    )
