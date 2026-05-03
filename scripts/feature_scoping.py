#!/usr/bin/env python3
"""Draft a lightweight spec on a Linear issue tagged ``needs-spec`` and
post it as a comment.

Triggered by .github/workflows/feature-scoping.yml when the
linear-label-router detects an issue with the ``needs-spec`` label that
does not also have ``spec-drafted`` or ``auto/refused-safety``. Calls
Anthropic API directly via stdlib http for the spec drafting.

This is the only one of the three router-triggered scripts that needs
LLM reasoning. Refuses Tier 3 work outright (coach prompt, encryption,
shadow flag flips, PHI migrations, golden thresholds, HealthKit scope,
credentials) by labeling ``auto/refused-safety`` and exiting.

Usage:
    python3 scripts/feature_scoping.py <linear_issue_identifier>

Env: LINEAR_API_KEY, ANTHROPIC_API_KEY (both required).
"""

from __future__ import annotations

import datetime
import json
import os
import re
import sys
import urllib.error
import urllib.request

from lib_linear import (
    add_label,
    get_issue,
    has_label,
    post_comment,
)

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
ANTHROPIC_VERSION = "2023-06-01"
MAX_OUTPUT_TOKENS = 2000

TIER3_PATTERNS = [
    r"\bcoach[\s_-]*prompt\b",
    r"\bsafety[\s_-]*gate",
    r"\bencryption\b",
    r"\bencrypted[\s_-]*string\b",
    r"\bshadow[\s_-]*flag",
    r"\bml_shadow_",
    r"\bevidence[\s_-]*bound",
    r"\bgolden[\s_-]*threshold",
    r"\bgolden[\s_-]*data\b",
    r"\bhealthkit[\s_-]*scope",
    r"\bphi[\s_-]*migrat",
    r"\bcredential[s]?\b.*\b(rotat\w*|chang\w*|modif\w*)\b",
    r"\b(rotat\w*|chang\w*|modif\w*)\b.*\bcredential[s]?\b",
]


def _looks_tier3(text: str) -> str | None:
    """Returns the first matched pattern if the text describes a Tier 3
    change, else None."""
    if not text:
        return None
    lower = text.lower()
    for pattern in TIER3_PATTERNS:
        if re.search(pattern, lower):
            return pattern
    return None


def _anthropic_request(system_prompt: str, user_message: str) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY not set in env", file=sys.stderr)
        sys.exit(2)
    payload = json.dumps({
        "model": ANTHROPIC_MODEL,
        "max_tokens": MAX_OUTPUT_TOKENS,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_message}],
    }).encode("utf-8")
    req = urllib.request.Request(
        ANTHROPIC_API_URL,
        data=payload,
        headers={
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        print(f"Anthropic HTTP {e.code}: {detail}", file=sys.stderr)
        sys.exit(3)
    except Exception as e:  # noqa: BLE001
        print(f"Anthropic request failed: {e}", file=sys.stderr)
        sys.exit(3)
    parts = body.get("content", [])
    if not parts:
        print(f"Empty Anthropic response: {body}", file=sys.stderr)
        sys.exit(4)
    return "".join(p.get("text", "") for p in parts if p.get("type") == "text")


SPEC_SYSTEM_PROMPT = """You are a senior software engineer drafting a lightweight spec for Brock, the solo founder of Meld (iOS health coaching app, FastAPI backend, ML signal engine, Astro marketing site). Brock is product-trained, not engineering-trained, so write for clarity over jargon. Match Meld's voice: direct, no em dashes ever, no AI tells like "I'd be happy to" or "I'm excited to".

Return ONLY a Linear comment body in markdown using this exact structure (replace the fields, do not change the headings):

```
### Auto-draft spec, YYYY-MM-DD

**Problem**
One sentence. What the user or dev is trying to accomplish.

**Proposed solution**
2-4 sentences. High-level approach.

**Affected files**
- path/to/file1.py
- path/to/file2.swift
(5-10 files max; use plausible paths in this codebase. backend/ for FastAPI, Meld/ for iOS, website/ for Astro, evals/ for evals.)

**Test plan**
- What existing tests cover this
- What new tests would need to be added
- Any golden-data or snapshot updates

**Estimated complexity**
Small (<100 lines) / Medium (100-300) / Large (300-500) / Too-big (>500, split first).

**Tier classification (per HITL v2)**
Tier 0 (engineering, auto-merges) / Tier 2 (product, Brock reviews) / Tier 3 (refused, see reason).

**Open questions**
(3 max; Brock answers in Linear or leaves blank)
```

Hard rules:
- No em dashes anywhere. Use commas, colons, parens, sentence breaks.
- Do not invent file paths that obviously do not exist (no "fictional" files; if you do not know the precise path, say "in the relevant {area} module").
- If the issue is genuinely ambiguous, set Open questions to clarifying questions and Estimated complexity to "Unknown until clarified".
- Cap output at ~500 words."""


def _build_user_message(issue: dict) -> str:
    title = issue.get("title", "")
    description = issue.get("description") or "(no description)"
    comments = issue.get("comments", {}).get("nodes", [])
    recent_comment_strs = []
    for c in comments[-5:]:
        author = (c.get("user") or {}).get("name") or "?"
        body = c.get("body") or ""
        recent_comment_strs.append(f"- [{author}] {body[:300]}")
    comments_str = "\n".join(recent_comment_strs) or "- (no comments)"

    return f"""Issue: {issue.get("identifier", "?")}
Title: {title}

Description:
{description[:3000]}

Recent comments:
{comments_str}

Draft a spec for this issue using the structure in the system prompt."""


def _refusal_comment(reason: str, matched_pattern: str) -> str:
    return f"""### Auto-draft spec, refused

This issue describes a change that triggers the Tier 3 refuse list (matched pattern: `{matched_pattern}`). Tier 3 changes (coach prompt, safety gates, encryption, shadow flag flips, PHI migrations, golden thresholds, HealthKit scope, credentials) must be authored by Brock and cannot be auto-drafted.

If this is a false positive, edit `.github/hitl-config.json` and remove the relevant pattern, or rephrase the issue to avoid the trigger keyword.

Adding the `auto/refused-safety` label so this is not retried.

---
Filed by `.github/workflows/feature-scoping.yml`. Reason: {reason}."""


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: feature_scoping.py <linear_issue_identifier>", file=sys.stderr)
        return 2
    identifier = sys.argv[1]
    issue = get_issue(identifier)

    if has_label(issue, "spec-drafted"):
        print(f"{identifier} already has spec-drafted label; skipping", file=sys.stderr)
        return 0
    if has_label(issue, "auto/refused-safety"):
        print(f"{identifier} already refused; skipping", file=sys.stderr)
        return 0

    title = issue.get("title", "")
    description = issue.get("description") or ""
    combined = f"{title}\n{description}"
    matched = _looks_tier3(combined)
    if matched:
        body = _refusal_comment(reason="title or description matched a Tier 3 keyword", matched_pattern=matched)
        url = post_comment(issue["id"], body)
        print(f"Posted refusal: {url}", file=sys.stderr)
        current_label_ids = [n["id"] for n in issue["labels"]["nodes"]]
        add_label(issue["id"], current_label_ids, "auto/refused-safety")
        print(url)
        return 0

    user_message = _build_user_message(issue)
    spec_text = _anthropic_request(SPEC_SYSTEM_PROMPT, user_message).strip()
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    spec_text = spec_text.replace("YYYY-MM-DD", today)

    footer = f"\n\n---\nFiled by `.github/workflows/feature-scoping.yml`. Replaces the old `meld-feature-scoping` scheduled task. The `spec-drafted` label is the dedup signal."
    body = spec_text + footer
    url = post_comment(issue["id"], body)
    print(f"Posted drafted spec: {url}", file=sys.stderr)

    current_label_ids = [n["id"] for n in issue["labels"]["nodes"]]
    add_label(issue["id"], current_label_ids, "spec-drafted")
    print(f"Added spec-drafted label to {identifier}", file=sys.stderr)
    print(url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
