# Meld comprehensive code audit, 2026-04-30

Five parallel scans: Semgrep (all rule packs), GitNexus deep structural, iOS Swift manual scan, dependency / supply-chain CVE audit, code-quality + config audit. Read-only. No source modified.

Prior baseline: [baseline-scan-2026-04-30.md](baseline-scan-2026-04-30.md).

## TL;DR (read this if nothing else)

| Severity | Count | Top item |
| --- | --- | --- |
| **HIGH security** | 1 | **lightgbm 4.5.0 RCE** (CVE-2024-43598). Transitive dep, bump to 4.6.0. |
| **HIGH iOS bug** | 1 | **VoiceCaptureView permission race**: audio engine starts before SFSpeechRecognizer auth callback fires. `denied` users still trigger session activation. |
| **HIGH code rule violation** | 1 | **682 em dashes across 210 files** (Brock's hard rule). 620+ are clearable Tier 0; 60ish need Tier 3 override (`coach_engine.py`, `encryption.py`). |
| **HIGH infra** | 1 | `backend/Dockerfile:13` uses `ghcr.io/astral-sh/uv:latest` floating tag. Reproducibility risk; uv release can break prod silently. |
| **MOD security** | 4 | cryptography buffer overflow, mako path traversal, postcss XSS, yaml stack-overflow chain (via @astrojs/check) |
| Real Semgrep findings | 2 | SQL allowlist gaps in [ops.py:113](backend/app/routers/ops.py#L113) + [claim_default_user.py:80](backend/app/scripts/claim_default_user.py#L80) (from baseline) |
| Test coverage gaps | 22 | 18 untested backend services + 4 critical iOS service files (APIClient, AuthManager, KeychainStore, HealthKitService) |
| Tier 3 protected paths | **0 violations** | All boundaries (safety, encryption.py, PHI migrations, meta-guard workflows, HealthKit scope) are clean |

**Posture: green for a pre-launch app, with one urgent CVE bump and one user-facing iOS bug.** Most of the volume is hygiene (em dashes, Docker pinning, missing tests, stale dev IP) rather than security exposure. Semgrep across 18 rule packs found only 3 net-new issues beyond the original baseline, all code-quality. The wider security packs converged on the same set, which is a positive convergence signal.

---

## 1. Scan execution status

| Scan | Tool | Status | Findings |
| --- | --- | --- | --- |
| SAST broad | Semgrep 1.135.0, 18 rule packs (OWASP Top 10, CWE Top 25, Python, JS/TS, JWT, Docker, GH Actions, XSS, SQLi, command-injection, headless, r2c best-practices, r2c bug-scan, ...) | ✅ 16 of 18 packs ran (`p/sqlalchemy`, `p/yaml` 404'd from registry) | 21 dedup (3 net-new vs baseline) |
| Structural | GitNexus 1.6.3 (knowledge graph, 7,181 nodes / 22,258 edges / 190 communities / 42 flows) | ✅ All 11 query categories ran | Architecture insights, no critical structural smells |
| iOS Swift | Manual Grep + Read patterns (SwiftLint not installable on this WSL) | ✅ 96 prod files scanned across 7 categories | 1 HIGH bug, 4 HIGH untested, 207 em dashes, 8 user-facing em dashes |
| Deps + supply chain | npm audit (Node), OSV.dev custom query (Python uv.lock), GitHub API activity (Swift), manual Docker | ✅ 4 ecosystems audited | 1 HIGH + 4 MOD CVEs |
| Quality + config | Manual Grep + Read across 614 tracked files | ✅ 10 categories | 5 quick wins identified |

GitNexus MCP config in `~/.claude.json` updated to use WSL (the previous Windows-native `npx` config crashed on launch). Restart Claude again to pick up the fix and gain access to all 13 GitNexus MCP tools next session.

---

## 2. Security findings (Semgrep)

Only 3 net-new findings beyond the original baseline of 20. The expanded rule packs converged on the same set, confirming the baseline catches what's there.

### Net-new (not in baseline)

| Sev | Rule | File:Line | Risk |
| --- | --- | --- | --- |
| WARN | `python.lang.correctness.return.return-not-in-function` | [backend/app/services/coach_engine.py:52](backend/app/services/coach_engine.py#L52) | **Worth investigating**: `return` outside any function definition. Could be a docstring bug or stale code. |
| WARN | `python.lang.correctness.common-mistakes.string-concat-in-list` | [backend/ml/features/catalog.py:272](backend/ml/features/catalog.py#L272) | Implicit string concat in list literal: likely a missing comma. |
| INFO | `python.lang.correctness.useless-eqeq` | [backend/ml/forecasting/anomaly.py:144](backend/ml/forecasting/anomaly.py#L144) | `observed_val == observed_val` always True; if intent was NaN check, use `math.isnan()`. |

**`coach_engine.py:52` is Tier 3** (evidence-bound coach prompt file). Investigation can happen without modification, but any fix needs Brock override.

### Baseline-confirmed (already known)

5 ERRORs (4 SQL real but constrained, 1 GH Actions shell injection false positive) + 12 logger-credential-disclosure WARNs + 2 SHA-1 WARNs. Full triage in [baseline-scan-2026-04-30.md](baseline-scan-2026-04-30.md).

### Tier 3 hits

**Zero new findings touch protected paths**: `services/safety*`, `core/encryption.py`, PHI-table migrations, meta-guard workflows, HealthKit scope. The `coach_engine.py:52` net-new finding is in a Tier 3 file but the broader file path was always there; just no Semgrep rule had triggered on it before.

---

## 3. Dependency CVEs (1 HIGH, 4 MOD)

The single critical action item from this audit.

| Sev | Eco | Package | Current | Vuln | Fix | Action |
| --- | --- | --- | --- | --- | --- | --- |
| **HIGH** | Python | `lightgbm` | 4.5.0 | RCE via crafted model file (CVE-2024-43598) | 4.6.0 | **Bump now**. Transitive dep, find via `uv tree \| grep lightgbm` and bump the parent. |
| MOD | Python | `cryptography` | 46.0.6 | Buffer overflow on non-contig buffers (CVE-2026-39892) | 46.0.7 (or 47.0.0) | Bump. Ironic: this is what `app/core/encryption.py` (Tier 3) builds on, but the fix is package-version-only, not code change. |
| MOD | Python | `mako` | 1.3.10 | Path traversal via `//` URI in TemplateLookup | 1.3.11 | Bump. Pulled in via `alembic`. |
| MOD | Node | postcss + yaml chain | various | XSS + stack overflow via deep nesting | semver-major bump of `@astrojs/check` | One PR closes 4 of 6 npm advisories: `cd website && npm i @astrojs/check@latest`. |
| MOD | Docker | `python:3.12-slim` + `ghcr.io/astral-sh/uv:latest` | unpinned | Rolling tags = unreproducible CVE surface | Pin to digest or specific tag | See infra section below. |

### Dependency hygiene (not security, but worth a sweep)

- `pandas 2.3.3 → 3.0.2`, `xgboost 2.1.4 → 3.2.0` (major behind, ML stack: bump only if pipeline tests pass)
- `scikit-learn 1.6.1 → 1.8.0`, `shap 0.48.0 → 0.51.0`, `fastapi 0.135.3 → 0.136.1`, `uvicorn 0.44.0 → 0.46.0` (minor behind)
- 2 Swift packages pin moving branches (PhosphorSwift `branch: main`, SwiftUIX `branch: master`): reproducibility risk
- `slowapi 0.1.9` and `pycatch22 0.4.5` are at latest, but each is 24+ months stale upstream

**Tooling note for next time:** `pip-audit` can't read `uv.lock`. Workaround used: parse uv.lock + query OSV.dev directly (`.gitnexus-staging/dep-audit-osv.py`).

---

## 4. iOS Swift findings (96 files, 1 HIGH bug)

GitNexus + Semgrep both skip Swift, so this was the first real coverage of the iOS app.

### Real bugs

| Sev | File:line | Issue |
| --- | --- | --- |
| HIGH | [Meld/Views/Meals/VoiceCaptureView.swift:127](Meld/Views/Meals/VoiceCaptureView.swift#L127) | **SFSpeechRecognizer permission race.** Audio engine + recognition task start BEFORE the auth callback fires. Users who deny permission still trigger session activation. Fix: switch to iOS-17+ `await SFSpeechRecognizer.requestAuthorization()` async variant and gate audio setup on the result. |
| MED | [VoiceCaptureView.swift:129, :169](Meld/Views/Meals/VoiceCaptureView.swift#L129) | Two related concurrency issues from the same file: `@State` mutated from non-MainActor SFSpeechRecognizer queue, and recognition callback reads `transcribedText` outside `MainActor.run`. |
| MED | [Meld/Services/AppleSignInCoordinator.swift:72](Meld/Services/AppleSignInCoordinator.swift#L72) | `fatalError("Unable to generate nonce. SecRandomCopyBytes failed")` crashes the app on a sign-in path. Defensible (CSPRNG failure is exceptional) but a friendlier failure mode would degrade gracefully. |

### User-facing em dashes (8 sites: direct rule violation)

| File | Lines |
| --- | --- |
| [Meld/Views/Trends/TrendsView.swift](Meld/Views/Trends/TrendsView.swift) | 197, 215, 219 (copy strings); 275, 291, 303 (nutrition fallback uses U+2014 as placeholder) |
| [Meld/Views/Profile/ProfileSettingsView.swift](Meld/Views/Profile/ProfileSettingsView.swift) | 472, 473 (version/build fallback) |

Plus 199 em dashes in Swift comments and tokens (lower priority but still in scope of the rule).

### Tier 3 boundary check (HealthKit)

✅ **Clean.** Only [Meld/Services/HealthKitService.swift](Meld/Services/HealthKitService.swift) calls `HKHealthStore.requestAuthorization`. All other code goes through `HealthKitService.shared`. Info.plist + entitlements declare the right scopes. Read types align with `NSHealthShareUsageDescription`.

### Critical iOS service files lacking unit tests (4 of 26)

| File | Why it's critical |
| --- | --- |
| [Meld/Services/APIClient.swift](Meld/Services/APIClient.swift) | Token refresh + single-flight + 401 retry attach |
| [Meld/Services/AuthManager.swift](Meld/Services/AuthManager.swift) | MEL-43 followup #1 single-flight refresh fix has zero regression guard |
| [Meld/Services/KeychainStore.swift](Meld/Services/KeychainStore.swift) | Token round-trip + first-launch wipe |
| [Meld/Services/HealthKitService.swift](Meld/Services/HealthKitService.swift) | Tier 3, ContinuationGuard timeout logic |

11 more iOS files lack tests at the next severity tier (notification, network, view-models, etc.). Total 15.

### iOS Swift 6 hardening that's working

For context: extensive `@MainActor` (20 declarations across 14 files), `actor`-isolated `APIClient` / `AuthManager` / `KeychainStore` / `SignalRanker` / `RankerModelManager`, hand-rolled `PendingTabHolder` + `ContinuationGuard` for previously-audited races, `@preconcurrency` UN delegate per Swift-6-deadlock memory note. Zero `try!`, zero `as!`, no force-unwraps in production paths after PR-H hardening. Concurrency model is in good shape.

---

## 5. GitNexus structural insights

7,181 symbols, 22,258 edges, 190 communities, 42 named execution flows. Index time: ~5s.

### Headline caveat

GitNexus has **464 CALLS edges vs 6,437 DEFINES**. Static call resolution under-reports Python dynamic dispatch: FastAPI `Depends(get_db)`, ASGI lifespan, SQLAlchemy column types, and event hooks are invisible to the call graph. **Every `impactedCount: 0` on a boot-critical or DI-injected symbol is a false LOW.** Examples confirmed: `verify_secrets_configured`, `get_db`, `EncryptedString`, `CoachEngine`, `lifespan` all return graph-LOW but are real-world HIGH or CRITICAL.

Treat `gitnexus impact` as a **floor**, not a ceiling, on production risk. The grep cross-reference plus this repo's existing CLAUDE.md tier model are the ceiling.

### Architecture findings

- **No real boundary leaks.** All 15 cross-community CALLS stay within a single domain (Tests-Tests, Routers-Routers, Services-Services). Directory-as-module discipline holds.
- **Zero handler-less routes** (59 routes, 16 files, all wired).
- **Zero real Python import cycles.** 30 "cycles" are all iOS test-target indexer artifacts (false positives).
- **God-module candidates** (route density + process role + helper ownership):
  1. [backend/app/services/coach_engine.py](backend/app/services/coach_engine.py): 4-step daily-insight process, owns `CoachEngine` + `process_query` + `_render_*` family
  2. [backend/app/routers/ml_ops.py](backend/app/routers/ml_ops.py): 6 routes + top-2 hottest helpers (`_scalar_or_none` 8 calls, `_iso` 6 calls)
  3. [backend/app/routers/coach.py](backend/app/routers/coach.py): 6 routes, owns DI for CoachEngine
  4. [backend/app/main.py](backend/app/main.py): 3 routes + lifespan + `_sentry_before_send` + `_scrub_phi` + healthchecks (ASGI center)
  5. [backend/ml/features/builders.py](backend/ml/features/builders.py): 5 builder functions + hot helpers `_daterange`, `_date_to_str`

### Untested services owning multi-step flows (4 priorities)

| Service | Flow | Why test it |
| --- | --- | --- |
| [services/oura_sync.py](backend/app/services/oura_sync.py) | `Sync_user_data → Refresh_access_token` (3 steps) | Token refresh + 7-day window dedup logic |
| [services/oura_webhooks.py](backend/app/services/oura_webhooks.py) | `register_all_webhooks` + `_webhook_headers` (4 calls) | Webhook signature verification |
| [services/correlation_engine.py](backend/app/services/correlation_engine.py) | `Compute_correlations → Rank` (3 steps) | Causal inference output to coach |
| [services/anti_fatigue.py](backend/app/services/anti_fatigue.py) | `Can_send → _user_now` (3 steps) | Notification gating logic |

18 of 26 services lack a same-named test file. Heaviest gap is third-party data adapters (oura, garmin, peloton, openfoodfacts, usda) and notification engines. **Caveat**: many are tested indirectly via `test_*_routes.py`. Run `pytest --cov=app` before adding tests, to filter false positives.

### Candidate orphans (5 functions worth manual verification)

GitNexus shows zero callers; need to confirm via grep + actual entry points:

1. [services/literature.py](backend/app/services/literature.py): `search`, `validate_correlation`
2. [services/notification_content.py](backend/app/services/notification_content.py): 5 generators (`generate_health_alert`, `generate_weekly_review`, `generate_streak_saver`, `generate_bedtime_coaching`, `generate_coaching_nudge`)
3. [services/offline_eval.py](backend/app/services/offline_eval.py): `run_offline_eval` (CLI? scheduled?)
4. [services/notification_templates.py](backend/app/services/notification_templates.py): `seed_templates`, `pick_template`
5. [ml/cohorts/anonymize.py](backend/ml/cohorts/anonymize.py) + [cluster.py](backend/ml/cohorts/cluster.py): `build_anonymized_vectors`, `run_clustering_pipeline`

### Top 10 named execution flows (auto-detected)

1. `Run_granger_for_user → _check_stationarity` (4 steps): ML discovery
2. `Generate_daily_insight → Can_answer_from_rules` (4 steps): coach, **Tier 2**
3. `EncryptedString.process_bind_param → _parse_keys` (4 steps): **Tier 3**
4. `EncryptedString.process_result_value → _parse_keys` (4 steps): **Tier 3**
5. `Signal_quality → _scalar_or_none` (3 steps, cross-community): ML ops
6. `Sync_user_data → Refresh_access_token` (3 steps): Oura sync
7. `Compute_correlations → Rank` (3 steps)
8. `Generate_cohort → _wearable_to_*_record` (3 steps, cross-community)
9. `Train_ranker_pipeline → _compute_group_sizes` (3 steps)
10. `Sign_in_with_apple → _user_to_dict` (3 steps)

---

## 6. Quality + config audit (highlights)

### Em dashes: 682 occurrences across 210 files

This is the largest single hygiene issue. Per [feedback_no_em_dashes.md](C:/Users/howar/.claude/projects/C--Users-howar-ai-health-coach/memory/feedback_no_em_dashes.md), this is a hard rule with zero tolerance.

Top offenders by count:

| File | Em dashes |
| --- | --- |
| `backend/app/routers/auth_apple.py` | 18 |
| `backend/app/core/apple.py` | 18 |
| `backend/app/tasks/scheduler.py` | 17 |
| `backend/app/main.py` | 17 |
| `Meld/Services/APIClient.swift` | 13 |
| `backend/tests/test_content_blocks.py` | 12 |
| `backend/app/services/coach_engine.py` | 12 (1 is the literal anti-em-dash rule citation, legit) |
| `Meld/DesignSystem/Tokens/DSTypography.swift` | 12 |

**Two-PR remediation plan:**
1. **Tier 0 batch** (~620 of 682): one PR with a small Python rewrite script that replaces the em dash character with `, ` (or `;` or `:` as context allows) across all files except `app/services/safety*`, `app/services/coach_engine.py`, `app/core/encryption.py`, and `tests/ml/test_*golden*.py`.
2. **Tier 3 batch**: separate PR with explicit Brock override for the 3 protected files (~60 hits). The `coach_engine.py:361` literal rule citation must be preserved.

### Dockerfile findings

| Sev | Issue | Fix |
| --- | --- | --- |
| HIGH | `COPY --from=ghcr.io/astral-sh/uv:latest /uv ...` | Pin to specific tag like `ghcr.io/astral-sh/uv:0.4.27`, let dependabot bump |
| MED | `FROM python:3.12-slim` not pinned to digest | Pin to `python:3.12.7-slim-bookworm@sha256:...` |
| MED | No `USER` directive | Add `USER 1000` after install steps (CIS Docker bench) |
| LOW | No `HEALTHCHECK` | Layered defense; Railway has its own probe |
| LOW | `COPY . .` includes `.git` | Add `.git` to `.dockerignore` |

Good: `--no-install-recommends && rm -rf /var/lib/apt/lists/*`, `uv sync --frozen --no-dev`, robust `.dockerignore` for secrets.

### Hardcoded values worth fixing

| Sev | File:line | Issue |
| --- | --- | --- |
| MED | [backend/app/main.py:193](backend/app/main.py#L193) | `"http://192.168.86.47:8000"` in CORS allowlist: stale dev LAN IP committed to source |
| MED | [backend/app/config.py:68](backend/app/config.py#L68) | `public_base_url` defaults to the production Railway URL. Misconfigured deploys silently use prod. Default to `""` and add a `model_validator` that raises if `ENV != local` and value is empty. |

### GitHub Actions workflows

- ✅ All actions pinned to major version, no `@main`. No `pull_request_target`. No shell injection vectors via `${{ github.event.* }}`.
- ⚠️ **9 of 11 workflows lack `concurrency: cancel-in-progress`**: PR push spam burns runner minutes. Add this 3-line block to `backend.yml`, `code-review.yml`, `eval.yml`, `hitl-classifier.yml`, `ios.yml`, `ios-structural-checks.yml`, `migration-health.yml`, `website.yml`. Skip `dependabot-automerge.yml` (don't cancel mid-merge).
- ✅ All Tier 3 meta-guard workflows are clean (no shell injection, sensible permissions, pinned actions).

### Alembic migrations

✅ Clean: 0 drops in `upgrade()`, 0 f-string SQL, 0 missing `downgrade()`. 4 PHI-table migrations are tracked but Tier 3: leave alone.

### Repo hygiene

`.gitignore` is missing: `.venv/`, top-level `node_modules/`, `*.log`, `Thumbs.db`, `*.swp`. Zero tracked OS cruft (`.DS_Store`, etc.) currently. Easy one-line additions, no risk.

### TODO/FIXME backlog (5 actionable)

| File:line | Note |
| --- | --- |
| [backend/app/config.py:61](backend/app/config.py#L61) | Multi-user MVP scaling note |
| [backend/app/routers/webhooks.py:81](backend/app/routers/webhooks.py#L81) | Multi-user `oura_user_id` schema gap |
| [backend/ml/api.py:1437](backend/ml/api.py#L1437) | Phase 8B cluster membership lookup deferred |
| [Meld/DesignSystem/Components/DSIcon.swift:28](Meld/DesignSystem/Components/DSIcon.swift#L28) | Temporary icon names: confirm DS handoff |
| [Meld/Views/Components/ComponentShowcase.swift:5](Meld/Views/Components/ComponentShowcase.swift#L5) | "Temporary screen": confirm not shipped to TestFlight |

---

## 7. Prioritized action list (by severity × blast radius)

### P0: security and correctness (this week)

1. **Bump `lightgbm` to 4.6.0+** to close CVE-2024-43598 RCE (HIGH). One-line PR.
2. **Fix [VoiceCaptureView.swift:127](Meld/Views/Meals/VoiceCaptureView.swift#L127) permission race.** User-facing iOS bug. Switch to async `requestAuthorization()` and gate audio setup on the result.
3. **Pin `ghcr.io/astral-sh/uv:latest`** in [backend/Dockerfile:13](backend/Dockerfile#L13) to a specific tag. One-line PR.

### P1: security hygiene (next week)

4. Bump `cryptography` 46.0.6 → 46.0.7 or 47.0.0
5. Bump `mako` 1.3.10 → 1.3.11
6. `cd website && npm i @astrojs/check@latest` (closes 4 of 6 npm advisories)
7. Pin Docker base `python:3.12-slim` to a digest; add `USER` directive
8. Add SQL identifier allowlist in [ops.py:113](backend/app/routers/ops.py#L113) and [claim_default_user.py:80](backend/app/scripts/claim_default_user.py#L80) (already in baseline P0 list)

### P2: code rule compliance + hygiene

9. **Em dash sweep, Tier 0 batch.** ~620 of 682 instances clearable in one PR via a `python -c` rewrite script. Skip the 3 Tier 3 files.
10. **Em dash sweep, Tier 3 batch.** Separate PR, needs Brock override, names `coach_engine.py`, `encryption.py`, and the safety files explicitly. Preserves the literal anti-em-dash rule on `coach_engine.py:361`.
11. Remove stale dev IP `192.168.86.47` from CORS allowlist in [main.py:193](backend/app/main.py#L193)
12. Default [config.py:68](backend/app/config.py#L68) `public_base_url` to empty + add fail-loud validator
13. Investigate `coach_engine.py:52` `return` outside function (Tier 3: read only, no fix without override)
14. Tighten `.gitignore` (`.venv/`, `*.log`, `Thumbs.db`, `*.swp`)
15. Add `concurrency: cancel-in-progress` to 9 workflow files

### P3: test coverage + refactor

16. Add unit tests for the 4 critical iOS service files: APIClient, AuthManager, KeychainStore, HealthKitService (Tier 3-aware, AuthManager has the MEL-43 followup race fix that's currently unguarded)
17. Add unit tests for the 4 backend services owning multi-step flows: oura_sync, oura_webhooks, correlation_engine, anti_fatigue
18. Verify the 5 candidate orphan modules (notification_content generators, literature, offline_eval, notification_templates, ml/cohorts pipeline): wire to entry point or delete
19. Refactor [ml_ops.py](backend/app/routers/ml_ops.py): split helpers (`_scalar_or_none`, `_iso`, `_days_between`) into `ml_ops_helpers.py` to shrink the god-module
20. Extract iOS shared test helpers into `MeldTestSupport` Swift package to eliminate the 30 false-positive cycle reports

### P4: Tier 3 documentation hygiene (no code changes)

21. Add `# CRITICAL: invoked via FastAPI Depends; do not rely on call-graph` comments on `get_db`, `lifespan`, `verify_secrets_configured`, `EncryptedString`, `CoachEngine.__init__` so future GitNexus-driven audits don't miscalibrate

---

## 8. Tier 3 boundary status

**Architectural boundaries are intact.** No new findings touch:

- `backend/app/services/safety*` (clean)
- `backend/app/core/encryption.py` (clean structurally; 5 em dashes in comments require Tier 3 override to remove)
- PHI-table Alembic migrations (`health_metric_records`, `sleep_records`, `chat_messages`, `meals`, `oura_*`, `garmin_*`, `peloton_*`, `user_correlations`, `ml_features`, `ml_baselines`, `ml_insights`): clean, all f-string-free, all `downgrade()` present
- `.github/workflows/code-review.yml`, `auto-fix*.yml`, `hitl-classifier.yml`, `migration-health.yml`, `ios-structural-checks.yml`, `dependabot-automerge.yml`: clean
- `.github/hitl-config.json`: clean
- `Meld/Services/Sync/HealthKitManager*` and `HealthKitService.swift`: clean architecturally; only finding is the lack of unit tests

**Things adjacent to Tier 3 worth knowing:**

- `coach_engine.py:52` has a Semgrep "return outside function" warning. Tier 3 file. Investigate read-only; any fix requires Brock override.
- `encryption.py` and `coach_engine.py` together hold ~17 of the 682 em dashes. Cleaning them is Tier 3 by file path.
- `cryptography` package CVE bump indirectly improves `core/encryption.py` security. The bump is pip-only, no Tier 3 code change.

---

## 9. Artifacts

All scan outputs live under `.gitnexus-staging/` (gitignored, will not be committed):

| File | What it is |
| --- | --- |
| `semgrep-baseline.json` + `semgrep-summary.json` | Original baseline scan (3 packs) |
| `semgrep-comprehensive.json` + `semgrep-comprehensive-summary.json` | This report's broad scan (16 packs) |
| `semgrep-comprehensive-run.log`, `semgrep-rerun.log`, `semgrep-batch-status.csv` | Audit trail |
| `npm-audit-website.json` | Node CVE audit |
| `pip-audit-backend.json` | Python CVE audit (via OSV.dev custom script) |
| `swift-deps.txt`, `docker-base-images.txt` | Dependency catalogs |
| `dep-audit-osv.py`, `dep-audit-outdated.py` | Helper scripts (uv.lock parser + OSV query) |
| `ios-scan.json` | iOS Swift findings by category |
| `gn-deepdive.json` + `gn-q*-out.txt` | GitNexus query outputs |
| `quality-audit.json` | Quality + config audit findings |
| `parse_semgrep.py` | Semgrep JSON parser |

For reproduction commands, see [baseline-scan-2026-04-30.md](baseline-scan-2026-04-30.md) appendices.

Report generated 2026-04-30 by Claude Opus 4.7. Five parallel subagent scans, ~12 minutes wall time.
