"""ML-only configuration. Read via ``get_ml_settings()``.

Kept separate from ``backend.app.config`` so that importing ``backend.ml.config``
never triggers the main-app settings load, and so that ML shadow flags can be
toggled without restarting the whole API (hot-reloadable from env).

**Shadow-mode invariant**: every user-visible ML feature defaults to shadow-on
(`True`) until the operator flips it in env. When shadow is True, the model
runs and logs but does not affect user surfaces.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MLSettings(BaseSettings):
    """Environment-driven ML configuration.

    All ``ml_shadow_*`` flags default to True. A phase "goes live" only when
    the operator explicitly flips its shadow flag to False in Railway env.
    """

    model_config = SettingsConfigDict(
        env_prefix="ML_",
        env_file=".env",
        extra="ignore",
    )

    # ── Shadow-mode gates. True = run + log, do NOT surface. False = live. ──
    ml_shadow_feature_store: bool = Field(
        default=True,
        description="Phase 1: feature materialization pipeline runs but downstream does not read from it.",
    )
    ml_shadow_baselines: bool = Field(
        default=True,
        description="Phase 2: L1 STL + BOCPD baselines run but do not affect associations or anomalies.",
    )
    ml_shadow_associations: bool = Field(
        default=True,
        description="Phase 3: new L2 associations run in parallel with legacy correlation_engine.py.",
    )
    ml_shadow_insight_card: bool = Field(
        default=True,
        description="Phase 4: SignalInsightCard replaces CoachInsightCard. Shadow = fallback to old card.",
    )
    ml_shadow_coach_patterns: bool = Field(
        default=True,
        description="Phase 5: load_active_patterns feeds coach prompt. Shadow = use hardcoded KnowledgeGraph.",
    )
    ml_shadow_granger_causal: bool = Field(
        default=True,
        description="Phase 6: L3 + L4 results populated but confidence_tier promotion gated off.",
    )
    ml_shadow_coreml_ranker: bool = Field(
        default=True,
        description="Phase 7: learned XGBoost ranker. Shadow = fall back to heuristic ranker on device.",
    )
    ml_shadow_cohorts: bool = Field(
        default=True,
        description="Phase 8: HDBSCAN cohort clustering. Opt-in UX gated behind this flag.",
    )
    ml_shadow_apte: bool = Field(
        default=True,
        description="Phase 9: APTE n-of-1 experiment mode visible in iOS.",
    )

    # ── MLflow tracking (Phase 10). ──
    mlflow_tracking_uri: str = Field(
        default="file:///tmp/mlflow",
        description="MLflow tracking server URI. Local filesystem in dev; self-hosted Railway URL in prod.",
    )
    mlflow_experiment_name: str = Field(
        default="meld-signal-engine",
        description="Default experiment name for all Signal Engine runs.",
    )

    # ── Cloudflare R2 for CoreML artifacts + DVC datasets. ──
    r2_endpoint_url: str = Field(
        default="",
        description="Cloudflare R2 S3-compatible endpoint. Empty in dev.",
    )
    r2_access_key_id: str = Field(default="")
    r2_secret_access_key: str = Field(default="")
    r2_bucket_models: str = Field(default="meld-models")
    r2_bucket_datasets: str = Field(default="meld-datasets")

    # ── Modal (heavy training offload). ──
    modal_token_id: str = Field(default="")
    modal_token_secret: str = Field(default="")

    # ── Discovery pipeline tuning. ──
    l2_min_sample_size: int = Field(default=14, description="Minimum paired n for L2 associations.")
    l2_max_pairs_per_run: int = Field(default=200, description="Cap on dynamic pair generation.")
    l2_fdr_alpha: float = Field(default=0.10, description="BH-FDR threshold (preserved from legacy engine).")
    l2_window_days: int = Field(default=30, description="Rolling window for associations.")
    l1_min_history_days: int = Field(default=28, description="Minimum observed days to compute a baseline.")

    # ── Forecasting. ──
    forecast_horizon_days: int = Field(default=7)
    forecast_min_history_days: int = Field(default=90)

    # ── Ranker. ──
    ranker_coldstart_label_threshold: int = Field(
        default=20,
        description="Minimum labeled pairs per user before switching from heuristic to learned ranker.",
    )
    ranker_max_candidates_per_user_per_day: int = Field(default=1)
    ranker_max_candidates_per_user_per_week: int = Field(default=3)

    # ── Cohort clustering (opt-in only). ──
    cohort_k_anonymity_threshold: int = Field(default=50)
    cohort_min_surface_size: int = Field(default=100)
    cohort_dp_epsilon: float = Field(default=1.0)

    # ── Synth factory (Phase 4.5). All synth rows tagged is_synthetic=True;
    # production aggregates and crisis eval buckets filter unconditionally. ──
    ml_shadow_synth_users: bool = Field(
        default=True,
        description="Phase 4.5: synth factory gate. True means synth data is generated and stored, but crisis eval and production aggregates filter it out by is_synthetic tag.",
    )
    synth_default_days: int = Field(
        default=120,
        description="Default cohort length. Covers L1 >=28, Prophet >=90, L3 Granger >=120.",
    )
    synth_default_generator: str = Field(
        default="parametric",
        description='"parametric" (scipy + numpy, always available) or "gan" (DoppelGANger, extras-gated).',
    )
    synth_adversarial_fraction: float = Field(
        default=0.20,
        description="Share of conversations seeded with adversarial personas (crisis, non-adherent, contrarian).",
    )
    synth_biometric_missingness_low: float = Field(
        default=0.12,
        description="Lower bound of target missingness for biometric features (hrv, sleep_efficiency, etc.).",
    )
    synth_biometric_missingness_high: float = Field(
        default=0.18,
        description="Upper bound of target missingness for biometric features.",
    )
    synth_manual_log_missingness_low: float = Field(
        default=0.35,
        description="Lower bound of target missingness for manual food logs.",
    )
    synth_manual_log_missingness_high: float = Field(
        default=0.50,
        description="Upper bound of target missingness for manual food logs.",
    )


@lru_cache(maxsize=1)
def get_ml_settings() -> MLSettings:
    """Return the cached MLSettings instance.

    LRU-cached so repeated calls are free. The instance re-reads env only when
    the process restarts, which matches the Railway deploy model.
    """
    return MLSettings()
