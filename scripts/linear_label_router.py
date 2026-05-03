#!/usr/bin/env python3
"""Poll Linear for trigger labels and dispatch the matching downstream
workflow_dispatch on each unprocessed match.

Triggered by .github/workflows/linear-label-router.yml on a 5-minute
cron. Replaces five PC-bound polling scheduled tasks
(meld-incident-response, meld-launch-checklist, meld-feature-scoping,
plus the autofix pollers covered separately).

Idempotency lives downstream: each handler (incident_response.py,
launch_checklist.py, feature_scoping.py) adds a marker label after it
runs. The router excludes issues with that marker via a Linear filter
(NOT-equals on the labels.name field).

Usage:
    python3 scripts/linear_label_router.py

Env: LINEAR_API_KEY (required), GITHUB_TOKEN (required, for
``gh workflow run`` dispatch).
"""

from __future__ import annotations

import os
import subprocess
import sys

from lib_linear import linear_request

REPO = "howard768/ai-health-coach"
MAX_DISPATCHES_PER_LABEL = 3


# Map: trigger label -> (downstream workflow file, marker label).
# Filter excludes issues that have the marker label OR auto/refused-safety
# (so a refused feature-scoping is not retried).
ROUTES = [
    ("priority/p0-outage", "incident-response.yml", "incident-playbook-initialized"),
    ("launch-check", "launch-checklist.yml", "launch-check-done"),
    ("needs-spec", "feature-scoping.yml", "spec-drafted"),
]


def _find_unprocessed(trigger_label: str, marker_label: str) -> list[dict]:
    """Linear has issues filtered by:
    - team is Meldhealth
    - state is not completed/canceled
    - labels.name contains trigger_label
    - labels.name does NOT contain marker_label OR auto/refused-safety
    """
    query = """
    query Find($trigger: String!) {
      issues(filter: {
        team: {id: {eq: "3c9f48bf-d007-4bf1-8c21-8f2b4b438110"}},
        state: {type: {in: ["backlog", "unstarted", "started"]}},
        labels: {name: {eq: $trigger}}
      }, first: 25) {
        nodes {
          id
          identifier
          title
          labels(first: 30) { nodes { name } }
        }
      }
    }
    """
    result = linear_request(query, {"trigger": trigger_label})
    nodes = result.get("data", {}).get("issues", {}).get("nodes", [])
    out = []
    for n in nodes:
        names = [lbl["name"] for lbl in n.get("labels", {}).get("nodes", [])]
        if marker_label in names:
            continue
        if "auto/refused-safety" in names:
            continue
        out.append(n)
    return out


def _dispatch_workflow(workflow_file: str, identifier: str) -> bool:
    """Fire ``gh workflow run <file> --field linear_issue_id=<identifier>``.
    Returns True on success."""
    try:
        subprocess.run(
            [
                "gh", "workflow", "run", workflow_file,
                "--repo", REPO,
                "--ref", "main",
                "--field", f"linear_issue_id={identifier}",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
        return True
    except subprocess.CalledProcessError as e:
        print(
            f"  gh workflow run {workflow_file} failed for {identifier}: "
            f"exit {e.returncode}\n  stderr: {e.stderr.strip()}",
            file=sys.stderr,
        )
        return False
    except Exception as e:  # noqa: BLE001
        print(f"  gh workflow run {workflow_file} crashed: {e}", file=sys.stderr)
        return False


def main() -> int:
    if not os.environ.get("LINEAR_API_KEY"):
        print("LINEAR_API_KEY not set", file=sys.stderr)
        return 2
    if not os.environ.get("GITHUB_TOKEN") and not os.environ.get("GH_TOKEN"):
        print("GITHUB_TOKEN/GH_TOKEN not set; gh workflow run will fail", file=sys.stderr)

    total_dispatched = 0
    for trigger, workflow, marker in ROUTES:
        unprocessed = _find_unprocessed(trigger, marker)
        if not unprocessed:
            print(f"[{trigger}] no unprocessed issues", file=sys.stderr)
            continue

        capped = unprocessed[:MAX_DISPATCHES_PER_LABEL]
        print(
            f"[{trigger}] {len(unprocessed)} unprocessed "
            f"(dispatching {len(capped)} -> {workflow})",
            file=sys.stderr,
        )
        for issue in capped:
            ident = issue["identifier"]
            ok = _dispatch_workflow(workflow, ident)
            if ok:
                total_dispatched += 1
                print(f"  -> dispatched {workflow} for {ident}", file=sys.stderr)

    print(f"OK dispatched {total_dispatched} workflow runs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
