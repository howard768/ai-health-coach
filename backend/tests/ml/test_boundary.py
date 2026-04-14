"""Boundary enforcement for ``backend.ml``.

The Signal Engine plan (``~/.claude/plans/golden-floating-creek.md``) locks in a
single rule: the rest of ``backend.app`` may only import ``backend.ml.api``.
Anything deeper is a boundary violation.

This test walks the AST of every .py file under ``backend/app/`` and fails if
any of them has an ``import backend.ml.X`` or ``from backend.ml.X import ...``
where X is anything other than ``api``. The same rule applies to the
path-less alias ``ml`` (tests run with cwd=backend so ``from ml import api``
is the legal canonical form).

Run: ``cd backend && uv run python -m pytest tests/ml/test_boundary.py -v``
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[2]
APP_DIR = BACKEND_ROOT / "app"
ML_DIR = BACKEND_ROOT / "ml"

# Canonical public surface. Add here if and only if a new top-level module in
# backend/ml/ is intentionally promoted to the public API.
ALLOWED_ML_IMPORT_TARGETS = frozenset({"api"})


def _iter_python_files(root: Path) -> list[Path]:
    """Return every .py file under root, excluding caches and virtualenvs."""
    return sorted(
        p
        for p in root.rglob("*.py")
        if "__pycache__" not in p.parts and ".venv" not in p.parts
    )


def _is_ml_path(dotted: str) -> bool:
    """Return True if the dotted path refers to the ML package.

    Matches ``ml``, ``ml.X``, ``backend.ml``, ``backend.ml.X``, and ``app.ml``
    variants. Anything else returns False.
    """
    if dotted in {"ml", "backend.ml", "app.ml"}:
        return True
    return any(
        dotted.startswith(prefix) for prefix in ("ml.", "backend.ml.", "app.ml.")
    )


def _ml_subpath(dotted: str) -> str:
    """Return the first segment under the ml root, or '' for the root itself.

    ``ml`` / ``backend.ml`` -> ``""``. ``backend.ml.api`` -> ``"api"``.
    ``backend.ml.features.store`` -> ``"features"``.
    """
    for prefix in ("backend.ml.", "app.ml.", "ml."):
        if dotted.startswith(prefix):
            rest = dotted[len(prefix) :]
            return rest.split(".", 1)[0]
    return ""


def _check_ast_for_violations(
    tree: ast.AST, filename: str = "<string>"
) -> list[str]:
    """Walk an AST and return a list of boundary-violation messages.

    Shared by ``_violations_in_file`` and the parametrized sanity tests so the
    exact same logic gets exercised. Returning a list (possibly empty) keeps
    the caller simple.
    """
    violations: list[str] = []

    for node in ast.walk(tree):
        # ``import X`` / ``import X as Y``
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if _is_ml_path(name):
                    target = _ml_subpath(name)
                    # Bare ``import ml`` / ``import backend.ml`` is disallowed;
                    # use ``from ml import api`` to get the public surface.
                    if target == "" or target not in ALLOWED_ML_IMPORT_TARGETS:
                        violations.append(
                            f"{filename}:{node.lineno} disallowed `import {name}`; "
                            f"use `from ml import api` (or `from backend.ml import api`)"
                        )

        # ``from X import Y``
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if not _is_ml_path(mod):
                continue
            target = _ml_subpath(mod)
            if target == "":
                # ``from ml import X`` / ``from backend.ml import X``
                # Every ``X`` must be on the public surface.
                bad = [
                    a.name
                    for a in node.names
                    if a.name not in ALLOWED_ML_IMPORT_TARGETS
                ]
                if bad:
                    violations.append(
                        f"{filename}:{node.lineno} disallowed "
                        f"`from {mod} import {', '.join(bad)}`; "
                        f"allowed: {sorted(ALLOWED_ML_IMPORT_TARGETS)}"
                    )
            else:
                # ``from ml.SOMETHING import X`` / ``from backend.ml.SOMETHING import X``
                if target not in ALLOWED_ML_IMPORT_TARGETS:
                    violations.append(
                        f"{filename}:{node.lineno} disallowed "
                        f"`from {mod} import ...`; "
                        f"allowed submodules: {sorted(ALLOWED_ML_IMPORT_TARGETS)}"
                    )

    return violations


def _violations_in_file(path: Path) -> list[str]:
    """Parse a single file and return boundary violations."""
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as e:
        return [f"{path}: syntax error at line {e.lineno}"]
    return _check_ast_for_violations(tree, filename=str(path))


# ─────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────


def test_ml_package_exists() -> None:
    """Sanity: the package we are guarding actually exists on disk."""
    assert ML_DIR.is_dir(), f"ml package not found at {ML_DIR}"
    assert (ML_DIR / "api.py").is_file(), "backend/ml/api.py must exist"
    assert (ML_DIR / "__init__.py").is_file(), "backend/ml/__init__.py must exist"


def test_no_app_code_imports_ml_internals() -> None:
    """The rest of backend.app may only reach into backend.ml.api.

    Anything deeper is a boundary violation. This test catches it at CI time.
    """
    all_violations: list[str] = []
    for path in _iter_python_files(APP_DIR):
        all_violations.extend(_violations_in_file(path))

    assert not all_violations, (
        "ML boundary violations found. The rest of backend.app may only import "
        "backend.ml.api (not any submodule).\n\n"
        + "\n".join(all_violations)
    )


def test_tests_outside_ml_respect_boundary() -> None:
    """Tests under backend/tests/ that are NOT in the ml/ subfolder must also
    respect the boundary. ``tests/ml/*`` is allowed to poke internals; every
    other test file should go through the public api.
    """
    tests_dir = BACKEND_ROOT / "tests"
    offenders: list[str] = []
    for path in _iter_python_files(tests_dir):
        try:
            rel = path.relative_to(tests_dir)
        except ValueError:
            continue
        if rel.parts and rel.parts[0] == "ml":
            continue
        offenders.extend(_violations_in_file(path))

    assert not offenders, (
        "Tests outside tests/ml/ violated the ML import boundary:\n"
        + "\n".join(offenders)
    )


@pytest.mark.parametrize(
    "good_import",
    [
        "from backend.ml import api",
        "from backend.ml.api import refresh_features_for_user",
        "import backend.ml.api",
        "from ml import api",
        "from ml.api import rank_candidates",
        "from app.services.health_data import get_latest_health_data",  # unrelated, must not flag
        "import json",  # unrelated, must not flag
    ],
)
def test_allowed_imports_are_recognized(good_import: str) -> None:
    """The walker must treat these forms as legal (zero violations).

    Uses the same ``_check_ast_for_violations`` function that runs against the
    real codebase.
    """
    tree = ast.parse(good_import)
    violations = _check_ast_for_violations(tree, filename="<good>")
    assert not violations, (
        f"False positive on legal import `{good_import}`: {violations}"
    )


@pytest.mark.parametrize(
    "bad_import",
    [
        "from backend.ml import features",
        "from backend.ml.features import store",
        "from backend.ml.discovery import associations",
        "import backend.ml.ranking",
        "from ml.forecasting import residuals",
        "import ml",  # bare package import is banned; use `from ml import api`
        "import backend.ml",
        "from backend.ml import api, features",  # mixed: partly legal, partly not
    ],
)
def test_disallowed_imports_are_flagged(bad_import: str) -> None:
    """The walker must flag every one of these as a violation."""
    tree = ast.parse(bad_import)
    violations = _check_ast_for_violations(tree, filename="<bad>")
    assert violations, f"Failed to flag illegal import `{bad_import}`"
