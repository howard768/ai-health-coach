#!/usr/bin/env python3
"""File or comment on a Linear issue when a health check fails.

Used by .github/workflows/health-checks.yml as the failure-path alert
mechanism. Replaced an earlier claude-code-action approach that turned out
to be unreliable (silent no-op on success, no actual Linear write).

Idempotent: searches for an OPEN issue (state types: backlog, unstarted,
started) with a matching title in the Meldhealth team. If found, appends
a comment. If not, creates a new issue with priority and `source/routine`
label set.

Reads `LINEAR_API_KEY` from the environment.

Usage:
    python3 scripts/file_linear_alert.py <priority> <title> <body> [<match_query>]

Where:
    priority      Linear priority int: 1=Urgent, 2=High, 3=Normal, 4=Low.
    title         Issue title used both for creation and (by default) for
                  the dedup search.
    body          Issue description on create, comment text on existing match.
    match_query   Optional. Comma-separated list of substrings tried in
                  order for the dedup search (instead of the title). The
                  first pattern that hits an open issue wins. Useful when
                  an existing tracker has a different title than the new
                  alert (e.g. pipeline-health checking against MEL-39
                  titled "Synth drift check..." while new alerts would
                  use "ML pipeline_freshness stale").

Prints the resulting issue or comment URL on stdout. Logs progress to stderr.
Exits 0 on success, non-zero on any API error.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
import urllib.error

LINEAR_API_URL = "https://api.linear.app/graphql"
TEAM_ID = "3c9f48bf-d007-4bf1-8c21-8f2b4b438110"  # Meldhealth
SOURCE_ROUTINE_LABEL_ID = "c6ee9f03-ba19-41b9-a4fd-c4a3ff96f11a"


def linear_request(query: str, variables: dict | None = None) -> dict:
    api_key = os.environ.get("LINEAR_API_KEY")
    if not api_key:
        print("LINEAR_API_KEY not set in env", file=sys.stderr)
        sys.exit(2)
    payload = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
    req = urllib.request.Request(
        LINEAR_API_URL,
        data=payload,
        headers={
            "Authorization": api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        print(f"Linear HTTP error {e.code}: {e.read().decode('utf-8', errors='replace')}", file=sys.stderr)
        sys.exit(3)
    except Exception as e:  # noqa: BLE001
        print(f"Linear request failed: {e}", file=sys.stderr)
        sys.exit(3)

    parsed = json.loads(body)
    if parsed.get("errors"):
        print(f"Linear GraphQL errors: {parsed['errors']}", file=sys.stderr)
        sys.exit(4)
    return parsed


def find_open_issue(match_query: str) -> dict | None:
    query = """
    query Search($team_id: ID!, $title_contains: String!) {
      issues(filter: {
        team: {id: {eq: $team_id}},
        state: {type: {in: ["backlog", "unstarted", "started"]}},
        title: {containsIgnoreCase: $title_contains}
      }, first: 5, orderBy: createdAt) {
        nodes { id identifier title }
      }
    }
    """
    result = linear_request(query, {"team_id": TEAM_ID, "title_contains": match_query})
    nodes = result.get("data", {}).get("issues", {}).get("nodes", [])
    return nodes[0] if nodes else None


def append_comment(issue_id: str, body: str) -> str:
    mutation = """
    mutation Comment($issue_id: String!, $body: String!) {
      commentCreate(input: {issueId: $issue_id, body: $body}) {
        success
        comment { id url }
      }
    }
    """
    result = linear_request(mutation, {"issue_id": issue_id, "body": body})
    comment = result["data"]["commentCreate"]["comment"]
    return comment["url"]


def create_issue(title: str, body: str, priority: int) -> str:
    mutation = """
    mutation Create($input: IssueCreateInput!) {
      issueCreate(input: $input) {
        success
        issue { id identifier url }
      }
    }
    """
    variables = {
        "input": {
            "teamId": TEAM_ID,
            "title": title,
            "description": body,
            "priority": priority,
            "labelIds": [SOURCE_ROUTINE_LABEL_ID],
        }
    }
    result = linear_request(mutation, variables)
    issue = result["data"]["issueCreate"]["issue"]
    return issue["url"]


def main() -> int:
    if len(sys.argv) < 4:
        print(
            "usage: file_linear_alert.py <priority> <title> <body> [<match_query>]",
            file=sys.stderr,
        )
        return 2
    priority_str, title, body = sys.argv[1], sys.argv[2], sys.argv[3]
    match_query = sys.argv[4] if len(sys.argv) > 4 else title
    try:
        priority = int(priority_str)
    except ValueError:
        print(f"priority must be an int, got {priority_str!r}", file=sys.stderr)
        return 2
    if priority not in (1, 2, 3, 4):
        print(f"priority must be 1-4, got {priority}", file=sys.stderr)
        return 2

    patterns = [p.strip() for p in match_query.split(",") if p.strip()]
    if not patterns:
        patterns = [title]
    existing = None
    matched_pattern = None
    for pattern in patterns:
        existing = find_open_issue(pattern)
        if existing:
            matched_pattern = pattern
            break

    if existing:
        print(
            f"Found existing {existing['identifier']} (\"{existing['title']}\") "
            f"via pattern {matched_pattern!r}; appending comment",
            file=sys.stderr,
        )
        url = append_comment(existing["id"], body)
    else:
        print(
            f"No existing OPEN issue matched any of {patterns!r}; "
            f"creating new (priority={priority})",
            file=sys.stderr,
        )
        url = create_issue(title, body, priority)
    print(url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
