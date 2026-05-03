#!/usr/bin/env python3
"""Initialize the incident-response playbook on a Linear P0 issue.

Triggered by .github/workflows/incident-response.yml when the
linear-label-router detects a new P0 issue without the
``incident-playbook-initialized`` label. Posts a structured playbook
comment + adds the marker label so the same issue is not processed twice.

Pure template fill. No Claude reasoning required. The 5 ``{placeholder}``
slots in the playbook get filled with live state pulled at run time
(deploy_sha, GitHub HEAD, recent CI failures, current timestamp).

Usage:
    python3 scripts/incident_response.py <linear_issue_identifier>

Env: LINEAR_API_KEY (required), GH_TOKEN or GITHUB_TOKEN (optional, used
to fetch CI run state via gh api; fallbacks to a stub if missing).
"""

from __future__ import annotations

import datetime
import json
import subprocess
import sys
import urllib.error
import urllib.request

from lib_linear import (
    add_label,
    get_issue,
    has_label,
    post_comment,
)

PROD_BACKEND = "https://zippy-forgiveness-production-0704.up.railway.app"
REPO = "howard768/ai-health-coach"


def _get_deploy_sha() -> str:
    try:
        with urllib.request.urlopen(f"{PROD_BACKEND}/ops/status", timeout=10) as resp:
            data = json.loads(resp.read())
        return (data.get("deploy_sha") or "")[:7] or "unknown"
    except Exception:  # noqa: BLE001
        return "unreachable"


def _get_main_head() -> str:
    """Best-effort: gh CLI if available, else direct GitHub API public read."""
    try:
        out = subprocess.run(
            ["gh", "api", f"repos/{REPO}/commits/main", "--jq", ".sha"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return out.stdout.strip()[:7]
    except Exception:  # noqa: BLE001
        try:
            with urllib.request.urlopen(
                f"https://api.github.com/repos/{REPO}/commits/main",
                timeout=10,
            ) as resp:
                return json.loads(resp.read())["sha"][:7]
        except Exception:  # noqa: BLE001
            return "unreachable"


def _recent_red_runs() -> list[str]:
    """Up to 3 most recent failed runs on main. Empty list on error."""
    try:
        out = subprocess.run(
            [
                "gh", "run", "list",
                "--repo", REPO,
                "--branch", "main",
                "--status", "failure",
                "--limit", "3",
                "--json", "displayTitle,workflowName,createdAt,url",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return [
            f"{r['workflowName']}: {r['displayTitle']} ({r['createdAt'][:16]}Z) {r['url']}"
            for r in json.loads(out.stdout)
        ]
    except Exception:  # noqa: BLE001
        return []


def _investigation_hints(title: str) -> list[str]:
    title_lower = title.lower()
    hints = []
    if any(k in title_lower for k in ("deploy", "release", "sha")):
        hints.append("Check `/ops/status.deploy_sha` vs GitHub `main` HEAD; Railway auto-deploy may have stalled.")
    if any(k in title_lower for k in ("database", "alembic", "migration")):
        hints.append("Check `Backend CI` workflow on the latest main commit, alembic round-trip step.")
    if any(k in title_lower for k in ("sentry", "5xx", "500", "exception")):
        hints.append("Open Sentry, filter to last 1h, look for spikes since the latest deploy.")
    if any(k in title_lower for k in ("scheduler", "cron", "job")):
        hints.append("Check `/ops/status.scheduler_running` and the `next_run` timestamps for stuck jobs.")
    if any(k in title_lower for k in ("ios", "apple", "apns", "testflight")):
        hints.append("Check TestFlight build status and APNs delivery records.")
    if any(k in title_lower for k in ("oura", "garmin", "peloton", "apple health")):
        hints.append("Check OAuth token validity and the relevant sync job logs in Railway.")
    if any(k in title_lower for k in ("ml", "feature", "synth", "drift", "pipeline")):
        hints.append("Check `/ops/status.pipeline_freshness` and recent ML scheduler job runs.")
    if not hints:
        hints.append("No specific keyword hits in the title; start with `/ops/status` and Sentry.")
    return hints


def _build_playbook(issue: dict, now_iso: str) -> str:
    deploy_sha = _get_deploy_sha()
    main_head = _get_main_head()
    red_runs = _recent_red_runs()
    hints = _investigation_hints(issue["title"])

    red_runs_str = (
        "\n".join(f"- {r}" for r in red_runs) if red_runs else "- (none in last 3 runs on main)"
    )
    hints_str = "\n".join(f"- {h}" for h in hints)

    return f"""### Incident Response Playbook (auto-initialized {now_iso})

**Severity**: P0 outage. Brock drives resolution.

## Checklist

- [ ] **Identify**, is production actually down? Run `curl {PROD_BACKEND}/ops/status` and `/readyz`. Note HTTP code + latency.
- [ ] **Contain**, if user-facing impact: post a status update (TestFlight, if applicable). If only internal: skip.
- [ ] **Diagnose**, link the Sentry event, the failing CI run, or the deploy SHA from `/ops/status`. Identify the change that introduced the regression.
- [ ] **Resolve**, revert, hotfix, or scale. For hotfixes, use the standard PR flow (no `--no-verify`).
- [ ] **Verify**, `/readyz` returns 200, `/ops/status.status` is "ok", any affected scheduled jobs have run successfully.
- [ ] **Postmortem**, within 48h: write a blameless postmortem in Obsidian under `Audits/`. Cover timeline, impact, root cause, what we learned, action items.

## Initial investigation hints

{hints_str}

## Auto-ops context (live at init)

- Production deploy_sha: `{deploy_sha}`
- GitHub main HEAD: `{main_head}`
- Recent failed CI on main:
{red_runs_str}

## Timeline

This comment is the start. Add timestamped entries below as steps complete. Format:
- `2026-04-17T14:32Z`, Confirmed outage, /readyz returns 503
- `2026-04-17T14:38Z`, Identified: last deploy f7abc...
- `2026-04-17T14:45Z`, Reverted via PR #42, merged
- `2026-04-17T14:52Z`, /readyz back to 200

---
Filed by `.github/workflows/incident-response.yml`. Replaces the old
`meld-incident-response` scheduled task. The `incident-playbook-initialized`
label is the dedup signal; this issue will not be processed again."""


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: incident_response.py <linear_issue_identifier>", file=sys.stderr)
        return 2
    identifier = sys.argv[1]
    issue = get_issue(identifier)

    if has_label(issue, "incident-playbook-initialized"):
        print(f"{identifier} already has incident-playbook-initialized label; skipping", file=sys.stderr)
        return 0

    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = _build_playbook(issue, now_iso)
    url = post_comment(issue["id"], body)
    print(f"Posted playbook comment: {url}", file=sys.stderr)

    current_label_ids = [n["id"] for n in issue["labels"]["nodes"]]
    add_label(issue["id"], current_label_ids, "incident-playbook-initialized")
    print(f"Added incident-playbook-initialized label to {identifier}", file=sys.stderr)
    print(url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
