# Meld

AI-powered health coach for iOS. Reads sleep, recovery, workouts, and nutrition data from Oura, Apple Health, Garmin, and Peloton, then talks to you about it like an actual coach who has seen the numbers.

## What's in this repo

| Path | What it is |
|---|---|
| `Meld/` | iOS app — SwiftUI 6, iOS 17+, custom design system, Sign in with Apple |
| `MeldNotificationServiceExtension/` | NSE for rich push notifications (recovery badges, etc.) |
| `MeldTests/` | iOS unit tests (XCTest) |
| `backend/` | FastAPI service — Python 3.13, async SQLAlchemy, Anthropic SDK, APScheduler |
| `evals/` | Promptfoo + pytest eval suite for the coach prompt (56 + 19 tests) |
| `Fonts/`, `medium/`, `eightsleep/` | Reference assets and supporting material |
| `project.yml` | XcodeGen source of truth — regenerate the .xcodeproj from this |
| `.github/workflows/` | CI: backend tests, iOS build, eval suite |

## Quick start

### Backend

```bash
cd backend
uv sync
cp .env.example .env  # add your ANTHROPIC_API_KEY, OURA_*, APNS_*, JWT_SECRET, etc.
uv run uvicorn app.main:app --reload --port 8000
```

Verify: `curl http://localhost:8000/healthz` should return `{"status":"ok"}`.

### iOS app

```bash
brew install xcodegen
xcodegen generate
open Meld.xcodeproj
```

Pick the **Meld** scheme and a recent iPhone simulator. The Debug build talks to your local backend at `192.168.x.x:8000` (set in `project.yml` — replace with your Mac's LAN IP). Release builds hit Railway.

### Eval suite

```bash
cd evals
uv sync
ANTHROPIC_API_KEY=... npx promptfoo eval        # 56 prompt tests
uv run python -m pytest                          # 19 quality gates
```

## Architecture at a glance

```
iPhone (SwiftUI)            Railway (FastAPI)              External
─────────────────           ──────────────────             ────────────
Meld app  ─── HTTPS ──>     /api/* + /auth/*    ─── HTTPS ──> Anthropic (Sonnet/Opus/Haiku)
                                  │                            Oura, Garmin, Peloton
                                  │                            APNs (push)
                                  ▼
                            SQLite (dev) / Postgres (prod)
                            APScheduler (background jobs)
```

The coach pipeline (`backend/app/services/coach_engine.py`) runs a 7-stage flow: deliberation routing → safety gating → tier selection (rules / Haiku / Sonnet / Opus) → evidence-bound prompt → response → safety re-check → logging. Every routing decision is captured for explainability.

The data reconciliation layer (`backend/app/services/data_reconciliation.py`) takes raw values from each source, applies a per-metric priority table (Oura wins for sleep, Garmin for steps, etc.), and writes a single canonical value to `health_metric_records`. The dashboard reads only canonical rows so the user never sees conflicting numbers for the same day.

## Auth

Sign in with Apple → backend exchanges identity token for our own short-lived HS256 JWT (15 min) + rotating refresh token (30 days, SHA256 in DB, reuse-detection on the chain). Tokens live in iOS Keychain (`kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly`). Account deletion calls Apple's `/auth/revoke` then DELETEs the user row, which CASCADEs across the 13 tenant tables.

## Security at rest

OAuth tokens (Oura, Garmin sessions, Peloton, Apple refresh) are encrypted with Fernet (AES-128-CBC + HMAC) via a SQLAlchemy `EncryptedString` TypeDecorator. The key lives in Railway env vars only — losing the DB without the key gets you ciphertext, not credentials. Legacy plaintext rows are still readable and re-encrypt on the next write.

## Notifications

Six categories (morning brief, coaching nudge, bedtime coaching, streak saver, weekly review, health alert) run on APScheduler in the user's local timezone. Each category goes through anti-fatigue gates (daily budget, quiet hours, frequency preference) before APNs delivery. The shared `_run_notification_job()` helper handles the boilerplate so adding a new category is ~20 lines.

## Testing strategy

| Layer | Stack | What it covers |
|---|---|---|
| Backend unit | pytest + httpx test client | Auth flows, encryption, coach routing, deliberator |
| Coach quality | Promptfoo + pytest | 56 prompt-level scenarios + 19 reading-level / faithfulness / uniqueness gates |
| Prompt parity | pytest | Eval YAML and production prompt must agree on 11 rules |
| iOS unit | XCTest | ViewModels, token decoding, dashboard state |
| CI | GitHub Actions | Backend pytest, ruff lint, iOS xcodebuild + test, eval suite on PRs |

## What's NOT in this repo

- The Anthropic API key, JWT secret, encryption key, APNs `.p8`, and Sign in with Apple `.p8` — all in Railway env vars and `.env` (gitignored).
- The `meld.db` SQLite file in the repo root is local dev only. Production uses Railway Postgres.
- The Obsidian wiki at `~/Documents/Obsidian Vault/HealthCoach/` holds research docs, audits, and design specs that aren't suitable for this repo.

## Status

Pre-beta. Internal use only. Ship gates: encrypted tokens, JWT auth, rate limiting, pytest+eval CI green, reconciled metrics dashboard, account deletion working end-to-end.

**All 55 findings from the 2026-04-10 full codebase audit are closed** as of 2026-04-11: 10/10 P0 ship blockers, 18/18 P1 urgent, 19/19 P2 important, 8/8 P3 nice-to-have. All three CI workflows (Backend CI, iOS CI, Coach Eval Suite) are green on `main`. Ready for TestFlight dogfooding to friends and family.
