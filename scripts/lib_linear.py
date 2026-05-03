"""Shared Linear GraphQL helpers used by the autonomous-ops Python scripts.

Each script under ``scripts/*.py`` that talks to Linear should import from
this module rather than re-implement urllib glue. The module is stdlib-only
so it can run on a vanilla GitHub-hosted runner without ``pip install``.

Reads ``LINEAR_API_KEY`` from the environment.

Constants below are pre-fetched IDs to avoid a get-or-create round trip on
every invocation. If a label is renamed in Linear, update the ID here.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

LINEAR_API_URL = "https://api.linear.app/graphql"
MELDHEALTH_TEAM_ID = "3c9f48bf-d007-4bf1-8c21-8f2b4b438110"

# Pre-fetched label IDs. Keep in sync with Linear; see scripts/file_linear_alert.py
# for the original "source/routine" reference.
LABEL_IDS: dict[str, str] = {
    "source/routine": "c6ee9f03-ba19-41b9-a4fd-c4a3ff96f11a",
    "type/maintenance": "803879b9-f86c-4620-a2da-bc8c27c40373",
    "incident-playbook-initialized": "48c3f993-4faa-420d-abcd-5c8a0a9575a4",
    "priority/p0-outage": "07fa4889-5205-42dd-9ad1-e90ebc880acc",
    "auto/refused-safety": "b71f5aa7-96d3-4128-97ff-fa4a83e09e84",
    "auto/budget-exceeded": "bfab902a-c04d-4f41-99a1-80439b8313f6",
    "launch-check": "9485e0dd-6641-4b89-8c22-204b3eee28b3",
    "launch-check-done": "f6641437-e60c-4541-9a02-44100e989f45",
    "needs-spec": "2a7c3321-f8f5-443b-8416-1ff4cd230fd6",
    "spec-drafted": "509658e7-e957-4ad2-80c4-fca3ed1d098f",
}


def linear_request(query: str, variables: dict | None = None) -> dict:
    """POST a GraphQL operation to Linear. Exits non-zero on transport or
    GraphQL errors; returns the parsed body otherwise."""
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
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        print(f"Linear HTTP {e.code}: {detail}", file=sys.stderr)
        sys.exit(3)
    except Exception as e:  # noqa: BLE001
        print(f"Linear request failed: {e}", file=sys.stderr)
        sys.exit(3)

    parsed = json.loads(body)
    if parsed.get("errors"):
        print(f"Linear GraphQL errors: {parsed['errors']}", file=sys.stderr)
        sys.exit(4)
    return parsed


def get_issue(identifier: str) -> dict:
    """Fetch an issue by identifier (e.g. "MEL-39") with description, labels,
    state, and the most recent 20 comments."""
    query = """
    query GetIssue($id: String!) {
      issue(id: $id) {
        id
        identifier
        title
        description
        url
        priority
        state { type name }
        labels(first: 20) { nodes { id name } }
        comments(first: 20) { nodes { id body createdAt user { name } } }
      }
    }
    """
    result = linear_request(query, {"id": identifier})
    issue = result.get("data", {}).get("issue")
    if not issue:
        print(f"No issue found with identifier {identifier!r}", file=sys.stderr)
        sys.exit(5)
    return issue


def post_comment(issue_id: str, body: str) -> str:
    """Append a comment to an issue. Returns the comment URL."""
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


def add_label(issue_id: str, current_label_ids: list[str], new_label_name: str) -> None:
    """Add a label to an issue without removing existing ones. Linear's
    issueUpdate replaces the entire labelIds array, so we must pass the union
    of current + new."""
    if new_label_name not in LABEL_IDS:
        print(f"Label {new_label_name!r} not in LABEL_IDS registry", file=sys.stderr)
        sys.exit(6)
    new_id = LABEL_IDS[new_label_name]
    if new_id in current_label_ids:
        return  # already present, no-op
    union = list({*current_label_ids, new_id})
    mutation = """
    mutation AddLabel($id: String!, $label_ids: [String!]) {
      issueUpdate(id: $id, input: {labelIds: $label_ids}) {
        success
      }
    }
    """
    linear_request(mutation, {"id": issue_id, "label_ids": union})


def has_label(issue: dict, label_name: str) -> bool:
    """Check if an issue already has a given label by name."""
    return any(
        node.get("name") == label_name
        for node in issue.get("labels", {}).get("nodes", [])
    )


def label_id(name: str) -> str:
    """Look up a label ID from the registry. Exits if missing."""
    if name not in LABEL_IDS:
        print(f"Label {name!r} not in LABEL_IDS registry", file=sys.stderr)
        sys.exit(6)
    return LABEL_IDS[name]
