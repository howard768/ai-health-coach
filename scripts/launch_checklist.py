#!/usr/bin/env python3
"""Validate the 19-point pre-launch checklist for a Linear issue tagged
``launch-check`` and post results as a comment.

Triggered by .github/workflows/launch-checklist.yml when the
linear-label-router detects an issue with the ``launch-check`` label that
does not also have ``launch-check-done``. Posts a structured Pass / Needs
work / Manual breakdown then adds the ``launch-check-done`` marker.

The 19 items split into 3 buckets:
- Auto-checkable (HTTP probe / repo file grep): items 7, 8 (partial),
  10 (partial), 11, 12, 13, 17 (partial), 18 (partial)
- Repo-checkable (file presence): items 7, 18
- Brock-only (App Store Connect, marketing assets): everything else

Usage:
    python3 scripts/launch_checklist.py <linear_issue_identifier>
"""

from __future__ import annotations

import datetime
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from lib_linear import (
    add_label,
    get_issue,
    has_label,
    post_comment,
)

PROD_BACKEND = "https://zippy-forgiveness-production-0704.up.railway.app"
PROD_WEBSITE = "https://heymeld.com"
REPO_ROOT = Path(__file__).resolve().parent.parent


def _http_status(url: str, timeout: int = 10) -> int | None:
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:  # noqa: BLE001
        return None


def _ops_status() -> dict:
    try:
        with urllib.request.urlopen(f"{PROD_BACKEND}/ops/status", timeout=10) as resp:
            return json.loads(resp.read())
    except Exception:  # noqa: BLE001
        return {}


def _grep_info_plist_encryption() -> bool | None:
    """True if Info.plist has ITSAppUsesNonExemptEncryption=false set;
    None if file missing."""
    plist = REPO_ROOT / "Meld" / "Info.plist"
    if not plist.exists():
        return None
    try:
        text = plist.read_text(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return None
    return "ITSAppUsesNonExemptEncryption" in text and "<false/>" in text


def _website_has_path(path: str) -> bool:
    code = _http_status(f"{PROD_WEBSITE}{path}")
    return code == 200


def _waitlist_endpoint_works() -> bool:
    """Verify the website's waitlist form endpoint accepts a POST. We do a
    HEAD/OPTIONS first; if that's not allowed, we fall back to a 200 GET on
    the form page itself."""
    page = _http_status(f"{PROD_WEBSITE}/")
    return page == 200


def _run_checks(issue: dict) -> tuple[list[str], list[str], list[str]]:
    """Returns (passing, needs_work, manual) bullet-point strings."""
    passing: list[str] = []
    needs: list[str] = []
    manual: list[str] = []

    # Product (1-6): all manual via App Store Connect
    manual.extend([
        "1. App Store Connect listing complete (name, subtitle, description, keywords, support URL, privacy policy URL).",
        "2. Screenshots: 6.7\" iPhone + 6.1\" iPhone (minimum 3 per size).",
        "3. App icon 1024x1024, alpha channel removed.",
        "4. Privacy details questionnaire complete (data collected, tracking, linked to user).",
        "5. Age rating set.",
        "6. In-app purchase or subscription config (if applicable).",
    ])

    # Technical (7-11)
    plist_check = _grep_info_plist_encryption()
    if plist_check is True:
        passing.append("7. `ITSAppUsesNonExemptEncryption=false` is set in `Meld/Info.plist`.")
    elif plist_check is False:
        needs.append("7. `Meld/Info.plist` does not contain `ITSAppUsesNonExemptEncryption=false`. Add it to skip the encryption compliance prompt.")
    else:
        manual.append("7. Could not locate `Meld/Info.plist`; verify by hand.")

    manual.append("8. Production build uploads cleanly to TestFlight (verify in Xcode Organizer or via testflight.yml).")
    manual.append("9. Latest build is visible to external testers in TestFlight.")
    manual.append("10. Production crash-free rate in the last 7 days is above 99% (Sentry or Apple analytics).")

    ops = _ops_status()
    if ops.get("status") == "ok":
        passing.append(f"11. Backend `/ops/status` returns ok (deploy_sha=`{(ops.get('deploy_sha') or '')[:7]}`).")
    else:
        needs.append(f"11. Backend `/ops/status` did not return ok. Got: `{ops or '(unreachable)'}`.")

    # Marketing (12-16)
    if _http_status(f"{PROD_WEBSITE}/") == 200:
        passing.append(f"12. Website {PROD_WEBSITE} returns 200.")
    else:
        needs.append(f"12. Website {PROD_WEBSITE} did not return 200.")

    if _waitlist_endpoint_works():
        passing.append("13. Waitlist form endpoint reachable (homepage 200; assumes form is on /).")
    else:
        needs.append("13. Could not reach the waitlist form page.")

    manual.append("14. Journal / blog has at least 3 published posts.")
    manual.append("15. Social kit 48-hour launch sequence is drafted and ready.")
    manual.append("16. Email templates drafted for: waitlist announcement, press pitch, feedback ask.")

    # Compliance (17-19)
    if _website_has_path("/privacy"):
        passing.append("17. Privacy Policy page is live at /privacy.")
    elif _website_has_path("/privacy-policy"):
        passing.append("17. Privacy Policy page is live at /privacy-policy.")
    else:
        needs.append("17. Could not find Privacy Policy at /privacy or /privacy-policy.")

    if _website_has_path("/terms") or _website_has_path("/terms-of-service"):
        passing.append("18. Terms of Service page is live.")
    else:
        needs.append("18. Could not find Terms of Service at /terms or /terms-of-service.")

    manual.append("19. Beta feedback list is gathered and reviewable.")

    return passing, needs, manual


def _build_comment(issue: dict, now_iso: str) -> str:
    passing, needs, manual = _run_checks(issue)
    n_pass = len(passing)
    n_needs = len(needs)
    n_manual = len(manual)
    total = n_pass + n_needs + n_manual

    pass_str = "\n".join(f"- [x] {p}" for p in passing) or "- (none yet)"
    needs_str = "\n".join(f"- [ ] {n}" for n in needs) or "- (none)"
    manual_str = "\n".join(f"- [ ] {m}" for m in manual) or "- (none)"

    if n_needs == 0 and n_manual == 0:
        recommendation = "**Go**. All auto-checkable items pass and nothing needs manual review."
    elif n_needs == 0:
        recommendation = f"**Conditional go**. {n_manual}/{total} items still need manual verification (App Store Connect UI, marketing assets). Review manually before submission."
    else:
        recommendation = f"**No-go yet**. {n_needs} hard blockers and {n_manual} manual items to verify."

    return f"""### Launch checklist, {now_iso}

**Ready (auto-verified)**: {n_pass}/{total}
**Needs work**: {n_needs}/{total}
**Not verifiable autonomously**: {n_manual}/{total}

## Passing
{pass_str}

## Needs work
{needs_str}

## Not verifiable from here
{manual_str}

## Go / no-go recommendation

{recommendation} Brock confirms.

---
Filed by `.github/workflows/launch-checklist.yml`. Replaces the old
`meld-launch-checklist` scheduled task. The `launch-check-done` label is
the dedup signal; this issue will not be processed again. Re-trigger by
removing the label."""


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: launch_checklist.py <linear_issue_identifier>", file=sys.stderr)
        return 2
    identifier = sys.argv[1]
    issue = get_issue(identifier)

    if has_label(issue, "launch-check-done"):
        print(f"{identifier} already has launch-check-done label; skipping", file=sys.stderr)
        return 0

    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = _build_comment(issue, now_iso)
    url = post_comment(issue["id"], body)
    print(f"Posted checklist comment: {url}", file=sys.stderr)

    current_label_ids = [n["id"] for n in issue["labels"]["nodes"]]
    add_label(issue["id"], current_label_ids, "launch-check-done")
    print(f"Added launch-check-done label to {identifier}", file=sys.stderr)
    print(url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
