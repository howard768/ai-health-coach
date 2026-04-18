#!/usr/bin/env python3
"""HITL classifier.

Classify a PR's changed files into tier0 (engineering auto-merge),
tier2 (product review), or tier3 (refuse and close).

Extracted from the inline heredoc in .github/workflows/hitl-classifier.yml
so the rules can be unit-tested (see test_hitl_classify.py) without
spinning up a PR. The behavior is identical to the prior inline version.

The workflow invokes this with:
  BASE_SHA=<sha> HEAD_SHA=<sha> GITHUB_OUTPUT=<path> \\
      python3 .github/scripts/hitl_classify.py

Reads:
  .github/hitl-config.json      classification rules
  changed_files.txt             one path per line (written by the diff step)

Writes to $GITHUB_OUTPUT the `tier`, `reasons`, and `matched_files` keys
that the downstream workflow steps consume.
"""

from __future__ import annotations

import fnmatch
import json
import os
import subprocess
import sys
from typing import Callable, Iterable


# Files for which we skip the content-match scan. Path-match still applies,
# so a credential (*.p8 / *.pem / .env) accidentally committed under any of
# these locations is still caught as Tier 3.
#
# Why these are safe to skip from content-match:
#   .github/workflows/*     workflow prompts enumerate the refuse list
#   .github/hitl-config.json  defines the needles themselves
#   .github/scripts/*       home of this classifier (docstrings, tests)
# Each of these legitimately references guard strings as metadata, not as
# shadow-flag flips. PR #44 was incorrectly closed as Tier 3 because its
# workflow prompt named those strings.
CONTENT_MATCH_SKIP_GLOBS: tuple[str, ...] = (
    ".github/workflows/*",
    ".github/hitl-config.json",
    ".github/scripts/*",
)


def matches_any(path: str, patterns: Iterable[str]) -> str | None:
    """Return the first pattern that matches `path`, or None."""
    for pat in patterns:
        if not any(c in pat for c in "*?["):
            if (
                path == pat
                or path.startswith(pat.rstrip("/") + "/")
                or path.startswith(pat)
            ):
                return pat
        if fnmatch.fnmatch(path, pat) or fnmatch.fnmatch(os.path.basename(path), pat):
            return pat
    return None


def skip_content_match(path: str) -> bool:
    for g in CONTENT_MATCH_SKIP_GLOBS:
        if fnmatch.fnmatch(path, g):
            return True
    return False


def classify(
    changed: list[str],
    cfg: dict,
    diff_for_path: Callable[[str], str],
) -> tuple[str, list[tuple[str, str]], list[tuple[str, str]], list[tuple[str, str]]]:
    """Classify changed files into a tier.

    `diff_for_path(path)` returns the unified diff body for that file,
    or "" when the diff cannot be produced.

    Returns (tier, tier3_path_hits, tier3_content_hits, tier2_path_hits).
    """
    tier3_path_hits: list[tuple[str, str]] = []
    tier2_path_hits: list[tuple[str, str]] = []
    for path in changed:
        hit3 = matches_any(path, cfg.get("tier3_refuse", []))
        if hit3:
            tier3_path_hits.append((path, hit3))
            continue
        hit2 = matches_any(path, cfg.get("tier2_product", []))
        if hit2:
            tier2_path_hits.append((path, hit2))

    tier3_content_hits: list[tuple[str, str]] = []
    content_needles = cfg.get("tier3_refuse_content_match", [])
    if content_needles and changed:
        for path in changed:
            if skip_content_match(path):
                continue
            diff = diff_for_path(path)
            added = [
                ln[1:]
                for ln in diff.splitlines()
                if ln.startswith("+") and not ln.startswith("+++")
            ]
            added_text = "\n".join(added)
            for needle in content_needles:
                if needle in added_text:
                    tier3_content_hits.append((path, needle))

    tier = "tier0"
    if tier3_path_hits or tier3_content_hits:
        tier = "tier3"
    elif tier2_path_hits:
        tier = "tier2"
    return tier, tier3_path_hits, tier3_content_hits, tier2_path_hits


def git_diff_provider(base_sha: str, head_sha: str) -> Callable[[str], str]:
    def inner(path: str) -> str:
        try:
            return subprocess.check_output(
                ["git", "diff", f"{base_sha}...{head_sha}", "--", path],
                text=True,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            return ""

    return inner


def format_reasons(
    tier3_path_hits: list[tuple[str, str]],
    tier3_content_hits: list[tuple[str, str]],
    tier2_path_hits: list[tuple[str, str]],
) -> list[str]:
    reasons: list[str] = []
    if tier3_path_hits:
        reasons.append("Path matches (Tier 3 refuse):")
        for p, pat in tier3_path_hits:
            reasons.append(f"  - `{p}` matched `{pat}`")
    if tier3_content_hits:
        reasons.append("Content matches (Tier 3 refuse):")
        for p, needle in tier3_content_hits:
            reasons.append(f"  - `{p}` contains `{needle}`")
    if tier2_path_hits:
        reasons.append("Path matches (Tier 2 product):")
        for p, pat in tier2_path_hits:
            reasons.append(f"  - `{p}` matched `{pat}`")
    return reasons


def main() -> int:
    with open(".github/hitl-config.json") as f:
        cfg = json.load(f)
    with open("changed_files.txt") as f:
        changed = [line.strip() for line in f if line.strip()]

    base_sha = os.environ.get("BASE_SHA", "")
    head_sha = os.environ.get("HEAD_SHA", "")
    diff_for_path = git_diff_provider(base_sha, head_sha)

    tier, t3_path, t3_content, t2_path = classify(changed, cfg, diff_for_path)
    reasons = format_reasons(t3_path, t3_content, t2_path)

    gh_output = os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        with open(gh_output, "a") as out:
            out.write(f"tier={tier}\n")
            out.write("reasons<<EOF\n")
            out.write("\n".join(reasons) + "\n")
            out.write("EOF\n")
            file_list = "\n".join(
                f"- `{p}`" for p, _ in (t3_path + t3_content + t2_path)
            )
            out.write("matched_files<<EOF\n")
            out.write(file_list + "\n")
            out.write("EOF\n")

    print(f"Classified as {tier}")
    for line in reasons:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
