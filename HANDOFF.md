# STATUS HANDOFF from Phase 4.5 synth factory session

**To**: Phase 5.9 Promptfoo active-patterns cases (held per the cold-start protocol), plus whoever picks up Phase 6.

**Date**: 2026-04-15.

**Branch**: `claude/synth-factory-phase-4-5`, open as PR [#2](https://github.com/howard768/ai-health-coach/pull/2) against `main` (draft while this document goes up, flipped to ready at the end of the session).

## Where the branch is

8 commits on top of `4f8be4b` (main after PR #1's CI repairs merged). Full sequence:

| SHA | Commit |
| --- | --- |
| `d38aca8` | Commit 1: foundation (config shadow flag + 7 synth settings, `ml/synth/__init__.py`, `CohortManifest` + `generate_synth_cohort` stub in `ml.api`) |
| `26e8ba8` | Commit 2: `dinner_hour` nutrition feature (closes legacy METRIC_PAIRS gap) |
| `d232b7c` | Commit 3: `is_synthetic` schema on 5 raw tables + migration `5f2e8a4c1d93` |
| `300a3fc` | chore: untrack stale `backend/app/schemas/__pycache__/` |
| `98c66e4` | merge of main (pulls PR #1's CI repairs) |
| `eddd575` | Commit 4: synth factory core (6 files at `backend/ml/synth/`) |
| `e51eeed` | Commit 5: drift monitoring at `backend/ml/mlops/evidently_reports.py` |
| `8426316` | Commit 5 follow-up: `synth_drift_job` wired into scheduler at daily 04:15 UTC |
| `a607fb4` | Commit 6: `ml_synth_runs` migration + manifest persistence |
| `44f3e47` | Commit 7: fidelity test suite (6 gates) + feedback diversity |
| (this SHA) | Commit 8: HANDOFF.md |

5-gate local CI green on every commit. **413 backend tests passing** (up from 316 at Commit 3 and 306 at the start of Phase 4.5).

## Fixtures green, Phase 5.9 unblocked

All six fidelity gates defined in `~/.claude/plans/phase-4.5-scaffolding.md` pass on a fresh cohort. See `backend/tests/ml/test_synth_fidelity.py`:

1. **Lag-0 association recovery.** 90-day synth user -> `refresh_features_for_user` -> `run_associations` surfaces at least one `UserCorrelation` at `developing+` tier.
2. **Cross-channel correlation floor.** 20-user 60-day cohort holds HRV vs RHR at r <= -0.20, readiness vs HRV at r >= 0.40, steps vs sleep_efficiency (same-day) at r >= 0.15.
3. **Magnitude consistency.** Per-day deep + rem + light seconds match total within 5%, AND `HealthMetricRecord.sleep_duration` equals `SleepRecord.total_sleep_seconds` within 1 second for the same (user, date).
4. **Missingness calibration.** 500-user cohort: biometric missingness in `[0.09, 0.21]` (midpoint 0.15); food-log missingness in `[0.32, 0.53]` (midpoint 0.425).
5. **Feedback diversity.** Chi-square goodness-of-fit vs uniform over (up, down, none) rejects at p < 0.001.
6. **End-to-end pipeline integration.** `generate_cohort(120 days)` -> `refresh_features_for_user` -> `run_associations` -> `run_daily_insights` -> `load_coach_signal_context`. `SignalContext.active_patterns` is non-empty and every pattern is `developing+` with both `source_metric` and `target_metric` set.

**The Phase 5.9 Promptfoo active-patterns awareness cases (held per the cold-start protocol) may now commit.** The shape `load_coach_signal_context` returns on a synth user is the same shape the coach router consumes in production; Promptfoo can assert against it directly.

## Load-bearing invariant

`test_steps_lag1_drives_sleep_efficiency` in `backend/tests/ml/test_synth_wearables.py`. Pooled Pearson r between `steps[t-1]` and `sleep_efficiency[t]` stays >= 0.30 on 60-day / 20-user data (L2 BH-FDR developing-tier floor at n >= 30). If this test ever fails, tune `SLEEP_EFF_STEPS_LAG_COEF` in `backend/ml/synth/wearables.py`; do NOT loosen the test threshold. Phase 5.9 Promptfoo fixtures depend on the pair continuing to surface.

## Public API added

```
ml.api.generate_synth_cohort(db, n_users, days=120, seed=None, generator="parametric")
    -> CohortManifest

ml.api.build_synth_drift_report(db, output_dir=None, run_id=None, threshold=0.05)
    -> DriftReportSummary
```

`generate_synth_cohort` writes `is_synthetic=True` rows to the 5 raw tables (`SleepRecord`, `ActivityRecord`, `HealthMetricRecord`, `MealRecord`, `FoodItemRecord`) plus a manifest row to `ml_synth_runs`. The existing nightly `feature_refresh_job` picks up the raw rows when called with a synth user id. Does not commit; caller owns the transaction.

`build_synth_drift_report` compares synth biometrics against real-user biometrics via a scipy KS test per canonical metric. When Evidently imports cleanly (Python 3.12 environments like Railway CI) it also renders a DataDrift HTML report; when Evidently fails to import (Python 3.14 local dev hits `ConfigError` from pydantic.v1 internals) the KS summary still lands and `html_path` returns `None`.

## Scheduler wiring

`synth_drift_job` runs daily at 04:15 UTC via APScheduler. Until a synth cohort has been generated on a given environment, the job logs `"dataset too small"` each morning. When a cohort exists, the KS summary kicks in automatically. Registration in `backend/app/tasks/scheduler.py`; tests in `backend/tests/ml/test_synth_drift_scheduler.py`.

## Shadow-flag safety

`ml_shadow_synth_users=True` by default (in `ml.config.MLSettings`). `generate_synth_cohort` has no caller in `backend/app/` code and no HTTP endpoint; an operator has to invoke it explicitly. This PR does NOT generate synth rows on deploy. Merging to main is safe; no production aggregates change behavior until an operator runs a cohort.

## Deferred items

Known scope we explicitly did NOT ship in Phase 4.5:

- **R2 upload for drift HTML.** `build_synth_drift_report` writes to local filesystem only. Adding R2 needs a boto3 dep and is premature without a first real synth run to store. `MLSettings` already has `r2_*` fields ready.
- **Feature-store source swap for drift.** Drift reads from `HealthMetricRecord` directly, partitioning on `is_synthetic`. Moving to `ml_feature_values` needs an `is_synthetic` column on the feature store + backfill + `feature_refresh_job` propagation; strictly bigger than Commit 5 itself.
- **Real DoppelGANger fit in `wearables_gan.py`.** The opt-in path currently delegates to the parametric generator once the extras import succeeds. A real GAN fit belongs in a Modal job, not inline.
- **Real Haiku dual-agent in `conversations.py`.** The default `LLMCallable` is deterministic template-driven. A `_make_haiku_callable()` helper is provided for callers (Phase 5.9) who want live dialogue variety.
- **Synth conversation DB persistence.** `ChatMessageRecord` has no `is_synthetic` column; conversations stay in-memory as `ConversationFragment` dataclasses for fixture serialization. Add the column + a persist path when synth transcripts need to survive across processes.

## Next

Phase 6 is open. L3 Granger + L4 DoWhy quasi-causal. Synth cohorts are now available as validation data: the fidelity suite proves the factory's Granger spurious-null mitigation (strong shared latent) works end to end against L2, which is the prerequisite for L3. Plan at `~/.claude/plans/golden-floating-creek.md`.

Remember to re-check `test_steps_lag1_drives_sleep_efficiency` and the full fidelity suite stay green whenever any coefficient in `backend/ml/synth/wearables.py` changes. They are the gate keeping the synth factory honest.
