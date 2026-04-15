"""Phase 4.5 Commit 4: wearables_gan import-gate tests.

Pins the opt-in invariant: without the ``meld-backend[synth-gan]``
extras installed, the GAN path must raise ImportError with the
actionable hint message, not a bare ``ModuleNotFoundError`` from deep
inside TensorFlow.

Run: ``cd backend && uv run python -m pytest tests/ml/test_synth_wearables_gan.py -v``
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-must-be-long-enough-for-hs256-aaaaaaaa")
os.environ.setdefault("ENCRYPTION_KEY", "T0TXLkHFSeZRYGIIejSFVkhQrvRE-bWLkwXSkkdWiKQ=")
os.environ.setdefault("ANTHROPIC_API_KEY", "fake-key-tests-dont-call-anthropic")

import importlib

import pytest

from ml.synth import wearables_gan


def test_module_imports_cleanly_without_tf() -> None:
    """Module top must not depend on tensorflow so the cold-boot test
    passes regardless of whether extras are installed."""
    # The fact that we got here (the import at the top of this file
    # succeeded) is the assertion.
    assert hasattr(wearables_gan, "generate_wearables_gan")


def test_raises_actionable_import_error_without_extras(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulate a missing ``tensorflow`` / ``ydata_synthetic`` install and
    verify the user-facing message names the install command."""
    # Hide the heavy modules from the import system for this test even
    # if they happen to be installed locally.
    for mod in ("tensorflow", "ydata_synthetic", "ydata_synthetic.synthesizers.timeseries"):
        monkeypatch.setitem(sys.modules, mod, None)  # type: ignore[arg-type]

    # Rebind the wearables_gan module to a fresh state so the patched
    # sys.modules is observed. Without this, Python caches any earlier
    # successful import.
    fresh = importlib.reload(wearables_gan)

    from datetime import date

    from ml.synth.demographics import generate_demographics

    demo = generate_demographics(n_users=1, seed=1)
    with pytest.raises(ImportError) as excinfo:
        fresh.generate_wearables_gan(demo, days=1, start_date=date(2026, 1, 1), seed=1)

    msg = str(excinfo.value)
    assert "synth-gan" in msg
    assert "parametric" in msg


def test_hint_constant_names_install_command() -> None:
    """Pin the actionable-message contract so a phrase change is intentional."""
    assert "uv sync --extra synth-gan" in wearables_gan._EXTRAS_HINT
