#!/usr/bin/env python3
"""Standalone tests for the HITL classifier.

Run: python3 .github/scripts/test_hitl_classify.py

No pytest dependency. Each test_ function raises AssertionError on failure
and the __main__ block prints a summary and exits non-zero on any failure.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from hitl_classify import classify, matches_any, skip_content_match  # noqa: E402


# Mirrors .github/hitl-config.json. Kept inline so the test doesn't depend on
# the on-disk config drifting.
CFG = {
    "tier3_refuse": [
        "backend/app/services/safety",
        "backend/app/core/encryption.py",
        ".env",
        "*.p8",
        "*.pem",
    ],
    "tier3_refuse_content_match": [
        "EVIDENCE_BOUND_SYSTEM_PROMPT",
        "ml_shadow_",
    ],
    "tier2_product": [
        "backend/app/services/coach",
        "backend/app/services/chat_stream",
        "Meld/DesignSystem/Tokens/",
        "Meld/Views/Onboarding/",
        "website/src/content/",
        "website/src/pages/",
    ],
}


def _diff(body: str):
    return lambda _path: body


def test_workflow_yaml_with_needle_in_prompt_is_tier0():
    """PR #44 regression: a workflow YAML mentioning EVIDENCE_BOUND_SYSTEM_PROMPT
    inside an agent prompt block must NOT be classified as Tier 3.

    This is the exact shape of the diff that closed PR #44, a new workflow
    under .github/workflows/ whose prompt body enumerates the refuse list.
    """
    diff = (
        "+            ## Safety refuse list (HARD STOP)\n"
        "+            - Any file containing the string EVIDENCE_BOUND_SYSTEM_PROMPT\n"
        "+            - Any file containing ml_shadow_ (flag FLIPS, not new definitions)\n"
    )
    tier, t3_path, t3_content, t2_path = classify(
        [".github/workflows/auto-fix-impl.yml"], CFG, _diff(diff)
    )
    assert tier == "tier0", (tier, t3_path, t3_content, t2_path)
    assert t3_content == [], t3_content


def test_hitl_config_edits_are_not_content_match():
    """Editing the hitl-config itself to add or remove needles is metadata,
    not a shadow flag flip. Content-match must skip it."""
    diff = '+    "EVIDENCE_BOUND_SYSTEM_PROMPT_V2",\n'
    tier, _, t3_content, _ = classify(
        [".github/hitl-config.json"], CFG, _diff(diff)
    )
    assert tier == "tier0", tier
    assert t3_content == [], t3_content


def test_non_workflow_file_with_needle_is_still_tier3():
    """Adding EVIDENCE_BOUND_SYSTEM_PROMPT outside the skip list is still
    a Tier 3 content match."""
    diff = "+EVIDENCE_BOUND_SYSTEM_PROMPT = 'hacked'\n"
    tier, _t3_path, t3_content, _t2 = classify(
        ["backend/app/services/coach/prompt.py"], CFG, _diff(diff)
    )
    assert tier == "tier3", tier
    assert (
        "backend/app/services/coach/prompt.py",
        "EVIDENCE_BOUND_SYSTEM_PROMPT",
    ) in t3_content


def test_credential_under_workflows_still_caught_by_path_match():
    """A credential accidentally committed under .github/workflows/ must still
    trip the path-match rule, the skip is content-match only."""
    tier, t3_path, _t3_content, _t2 = classify(
        [".github/workflows/leaked.pem"], CFG, _diff("")
    )
    assert tier == "tier3", tier
    assert any(pat == "*.pem" for _, pat in t3_path), t3_path


def test_env_file_under_workflows_still_caught():
    tier, t3_path, _, _ = classify(
        [".github/workflows/.env"], CFG, _diff("")
    )
    assert tier == "tier3", tier
    assert any(pat == ".env" for _, pat in t3_path), t3_path


def test_removed_lines_do_not_match():
    """Content-match only scans added lines (start with '+' but not '+++').

    A diff that REMOVES a needle should not trip the classifier.
    """
    diff = "-EVIDENCE_BOUND_SYSTEM_PROMPT = 'old'\n+pass\n"
    tier, _, t3_content, _ = classify(["backend/app/config.py"], CFG, _diff(diff))
    assert tier == "tier0", tier
    assert t3_content == [], t3_content


def test_diff_header_lines_do_not_match():
    """Lines like '+++ b/file' start with '+' but are headers, not added content."""
    diff = "+++ b/has_EVIDENCE_BOUND_SYSTEM_PROMPT_in_header\n+pass\n"
    tier, _, t3_content, _ = classify(["backend/app/config.py"], CFG, _diff(diff))
    assert tier == "tier0", tier
    assert t3_content == [], t3_content


def test_coach_path_is_tier2():
    tier, _, _, t2 = classify(
        ["backend/app/services/coach/engine.py"], CFG, _diff("")
    )
    assert tier == "tier2", tier
    assert t2 == [
        ("backend/app/services/coach/engine.py", "backend/app/services/coach")
    ], t2


def test_tier3_path_outranks_tier2():
    tier, t3_path, _, t2 = classify(
        [
            "backend/app/core/encryption.py",
            "backend/app/services/coach/engine.py",
        ],
        CFG,
        _diff(""),
    )
    assert tier == "tier3", tier
    assert ("backend/app/core/encryption.py", "backend/app/core/encryption.py") in t3_path
    assert t2 == [
        ("backend/app/services/coach/engine.py", "backend/app/services/coach")
    ], t2


def test_empty_change_list_is_tier0():
    tier, t3p, t3c, t2 = classify([], CFG, _diff(""))
    assert tier == "tier0", tier
    assert (t3p, t3c, t2) == ([], [], [])


def test_skip_content_match_predicate():
    assert skip_content_match(".github/workflows/foo.yml") is True
    assert skip_content_match(".github/workflows/auto-fix-impl.yml") is True
    assert skip_content_match(".github/hitl-config.json") is True
    assert skip_content_match(".github/scripts/hitl_classify.py") is True
    assert skip_content_match(".github/scripts/test_hitl_classify.py") is True
    assert skip_content_match("backend/app/services/coach/engine.py") is False
    assert skip_content_match("workflows/foo.yml") is False


def test_classifier_self_reference_is_not_content_match():
    """The classifier's own scripts are allowed to name guard strings in
    docstrings, comments, and test CFG. Adding or editing them should not
    trip content-match (path-match still applies for credentials)."""
    diff = "+# explains the guard: EVIDENCE_BOUND_SYSTEM_PROMPT and ml_shadow_\n"
    tier, _, t3_content, _ = classify(
        [".github/scripts/hitl_classify.py"], CFG, _diff(diff)
    )
    assert tier == "tier0", tier
    assert t3_content == [], t3_content


def test_matches_any_glob_and_prefix():
    assert matches_any("a/.env", [".env"]) == ".env"
    assert matches_any("certs/foo.pem", ["*.pem"]) == "*.pem"
    assert (
        matches_any("backend/app/services/coach/engine.py", ["backend/app/services/coach"])
        == "backend/app/services/coach"
    )
    assert matches_any("unrelated/file.py", ["backend/app/services/coach"]) is None


def _run_all() -> int:
    tests = [
        (name, fn)
        for name, fn in sorted(globals().items())
        if name.startswith("test_") and callable(fn)
    ]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS {name}")
        except AssertionError as e:
            print(f"FAIL {name}: {e}")
            failed += 1
    print(f"\n{len(tests)} tests, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run_all())
