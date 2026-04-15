"""Phase 4.5 synthetic data factory.

This package is internal to ``backend/ml/``. The public entry point is
``ml.api.generate_synth_cohort`` (see ``backend/ml/api.py``). Nothing in
this package is importable from ``backend/app/*`` per the boundary test
at ``backend/tests/ml/test_boundary.py``.

Modules (filled in subsequent Phase 4.5 commits):

    demographics    Synthea adapter for age, sex, BMI, comorbidities.
    wearables       Parametric timeseries generator (scipy + numpy).
                    Enforces a shared latent confounder across channels
                    so L3 Granger sees real joint dependence, not
                    independently-sampled noise (Shojaie & Fox 2021).
    wearables_gan   DoppelGANger generator, opt-in via the
                    ``meld-backend[synth-gan]`` extras install. TF
                    dependency isolated behind a lazy import.
    conversations   Claude Haiku dual-agent coach chat simulator. Every
                    string passes through
                    ``ml.narrate.voice_compliance.check_all`` before
                    row write.
    factory         Orchestrator. Writes to raw tables only, returns
                    ``CohortManifest`` (defined in ``ml.api``).

Commit 1 ships this package marker plus the public stub in
``ml.api.generate_synth_cohort``. Subsequent commits fill the modules.
"""
