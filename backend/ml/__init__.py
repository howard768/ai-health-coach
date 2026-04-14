"""Meld Signal Engine — ML / pattern recognition platform.

This is a greenfield ML service inside the existing FastAPI backend. Nothing
outside of this package may import anything deeper than ``backend.ml.api``.
That invariant is enforced by ``backend/tests/ml/test_boundary.py``.

See the full build plan at ``~/.claude/plans/golden-floating-creek.md`` and the
architecture master doc in Obsidian: ``HealthCoach/Signal Engine.md``.

Structure:

- ``api`` — the SOLE public entry point for the rest of ``backend.app``.
- ``config`` — shadow-mode flags, model paths, MLflow / R2 URIs.
- ``features`` — catch22 + rolling stats + custom builders, feature store.
- ``discovery`` — L1 baselines, L2 associations, L3 Granger, L4 DoWhy, L5 APTE.
- ``forecasting`` — seasonal-naive + Prophet ensemble, residual anomaly + BOCPD.
- ``ranking`` — XGBoost LambdaMART + CoreML export + shadow logging.
- ``cohorts`` — opt-in anonymized HDBSCAN archetypes (k-anonymity >= 50, DP).
- ``narrate`` — Opus translator + SHAP explainer.
- ``mlops`` — MLflow client wrapper, Evidently drift, Modal training entrypoint.

Heavy third-party imports (pandas, scipy, statsmodels, xgboost, prophet, dowhy,
econml, shap, mlflow, evidently, nannyml, coremltools) are lazy-imported inside
function bodies, never at module top level. This keeps FastAPI cold boot under
the 4-second budget on Railway.
"""

__all__ = ["api", "config"]
