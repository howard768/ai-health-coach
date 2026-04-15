"""DoppelGANger wearables path. Opt-in behind ``meld-backend[synth-gan]`` extras.

The parametric generator (``wearables.py``) is the default everywhere
because it ships with numpy + scipy (already in the backend deps) and
takes milliseconds per user. The GAN path exists as the secondary route
for research sessions that want a higher-fidelity joint distribution,
at the cost of pulling TensorFlow + ydata-synthetic and spending tens
of minutes per cohort on CPU.

Invariants:

1. **Lazy TF import.** The ``tensorflow`` + ``ydata_synthetic`` imports
   live inside ``generate_wearables_gan``, never at module top. Without
   this, the cold-boot test in ``tests/ml/test_cold_boot.py`` would
   fail on machines that have the extras installed.

2. **Clear failure when extras absent.** When the GAN extras are not
   installed, ``ImportError`` is reraised with an actionable message
   that names the install command, rather than the raw TF / ydata
   import error. Tests pin this behavior so an accidental import-path
   regression gets caught at CI time.

3. **Output shape identical to the parametric generator.** Both paths
   emit ``list[WearableDay]``, so the factory orchestrator can swap
   generators without any downstream conditional logic.

4. **All rows tagged ``is_synthetic=True`` downstream.** This module
   does not write to the database; the factory owns that tagging.
"""

from __future__ import annotations

from datetime import date

from ml.synth.demographics import Demographics
from ml.synth.wearables import WearableDay


# The single extras install command we surface in the ImportError.
# Kept as a module-level constant so the exact phrasing is
# pin-testable.
_EXTRAS_HINT = (
    "DoppelGANger generator requires the 'synth-gan' extras. Install with: "
    "`uv sync --extra synth-gan` (adds tensorflow + ydata-synthetic). "
    "The parametric generator (generator='parametric') is the default and "
    "has no extra-install requirement."
)


def generate_wearables_gan(
    demographics: list[Demographics],
    days: int,
    start_date: date,
    seed: int | None = None,
    biometric_missingness: tuple[float, float] = (0.12, 0.18),
) -> list[WearableDay]:
    """DoppelGANger-backed path. Lazy-imports TF only on first call.

    When ``meld-backend[synth-gan]`` is not installed, raises
    ``ImportError(_EXTRAS_HINT)`` so the caller can surface a clean
    hint rather than the raw ``ModuleNotFoundError`` from TensorFlow.
    """
    # Heavy imports lazy-inside the function body per invariant 1.
    try:
        import tensorflow  # noqa: F401  (presence check only)
        from ydata_synthetic.synthesizers.timeseries import (  # noqa: F401
            DoppelGANger,
        )
    except ImportError as exc:
        raise ImportError(_EXTRAS_HINT) from exc

    # Placeholder implementation: research-grade GAN training loops
    # belong in a Modal job, not inline in a request path. For the
    # Phase 4.5 commit, when the extras are installed we delegate to the
    # parametric path so the shape contract and downstream wiring are
    # still exercised end-to-end. Replacing this with an actual
    # DoppelGANger fit is a follow-up tracked in the scaffolding plan.
    from ml.synth.wearables import generate_wearables

    return generate_wearables(
        demographics=demographics,
        days=days,
        start_date=start_date,
        seed=seed,
        biometric_missingness=biometric_missingness,
    )


__all__ = ["generate_wearables_gan"]
