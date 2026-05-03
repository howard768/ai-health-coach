"""Em dash sweep: replace U+2014 with safer punctuation across tracked files.

Per CLAUDE.md / feedback_no_em_dashes.md, em dashes are a hard rule
violation anywhere in the repo. The comprehensive 2026-04-30 audit
counted 682 occurrences across 210 files.

Replacement strategy:
- Default: `—` -> `, ` (most em dashes are parenthetical-comma replacements)
- Inside string literals shaped `"—"` (used as a "no-data" placeholder
  in iOS Views): `"—"` -> `"--"`
- Tier 3 files (encryption.py, coach_engine.py) skipped here; handled
  in a separate Tier 3 PR with explicit Brock override
- tests/ml/test_*golden*.py skipped; golden test data is sacred per CLAUDE.md

Usage:
    python scripts/em_dash_sweep.py --dry-run   # report only
    python scripts/em_dash_sweep.py             # apply
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

EM_DASH = "—"

TIER3_SKIPS = {
    "backend/app/core/encryption.py",
    "backend/app/services/coach_engine.py",
}

# Files that intentionally contain em dashes as RUNTIME DATA. The em-dash
# sanitizer in services/content_blocks.py looks for the literal U+2014 to
# strip from coach output; replacing it would break the sanitizer. Same for
# the test file that exercises it.
TEST_DATA_SKIPS = {
    "backend/app/services/content_blocks.py",
    "backend/tests/test_content_blocks.py",
}


def is_tier3_skip(rel_path: str) -> bool:
    if rel_path in TIER3_SKIPS:
        return True
    if rel_path in TEST_DATA_SKIPS:
        return True
    if rel_path.startswith("backend/app/services/safety"):
        return True
    if rel_path.startswith("backend/tests/ml/test_") and "golden" in rel_path:
        return True
    return False


def is_binary(path: pathlib.Path) -> bool:
    """Cheap binary check: read first 8KB, look for NUL byte."""
    try:
        with path.open("rb") as f:
            return b"\x00" in f.read(8192)
    except (OSError, PermissionError):
        return True


def sweep_file(path: pathlib.Path, content: str) -> tuple[str, int]:
    """Return (new_content, replacements_made).

    Replacement rules, applied in order:
    1. ``"—"`` (em dash as a literal string placeholder, e.g. iOS "no data"
       fallback) becomes ``"--"`` so the visual shape is preserved.
    2. `` — `` (space, em dash, space; the parenthetical use) becomes ``, ``
       (single comma + space) so spacing collapses cleanly.
    3. Any remaining em dash becomes ``,`` with no surrounding spaces. This
       handles e.g. ``X—Y`` (compound) and end-of-line cases.
    """
    if EM_DASH not in content:
        return content, 0

    placeholder_count = content.count(f'"{EM_DASH}"')
    new_content = content.replace(f'"{EM_DASH}"', '"--"')

    spaced_pattern = f" {EM_DASH} "
    spaced_count = new_content.count(spaced_pattern)
    new_content = new_content.replace(spaced_pattern, ", ")

    bare_count = new_content.count(EM_DASH)
    new_content = new_content.replace(EM_DASH, ",")

    return new_content, placeholder_count + spaced_count + bare_count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="report only, do not write")
    parser.add_argument("--root", default=".", help="repo root")
    args = parser.parse_args()

    root = pathlib.Path(args.root).resolve()
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    tracked = [pathlib.Path(p) for p in result.stdout.splitlines() if p]

    total_replacements = 0
    files_touched = 0
    files_skipped_tier3 = 0
    files_skipped_binary = 0

    per_file: list[tuple[str, int]] = []

    for rel in tracked:
        if is_tier3_skip(str(rel).replace("\\", "/")):
            files_skipped_tier3 += 1
            continue
        path = root / rel
        if not path.is_file():
            continue
        if is_binary(path):
            files_skipped_binary += 1
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            continue
        new_content, n = sweep_file(path, content)
        if n == 0:
            continue
        per_file.append((str(rel).replace("\\", "/"), n))
        total_replacements += n
        files_touched += 1
        if not args.dry_run:
            path.write_text(new_content, encoding="utf-8")

    per_file.sort(key=lambda t: -t[1])
    print(f"=== Em dash sweep ({'DRY-RUN' if args.dry_run else 'APPLIED'}) ===")
    print(f"Files touched: {files_touched}")
    print(f"Total replacements: {total_replacements}")
    print(f"Tier 3 files skipped: {files_skipped_tier3}")
    print(f"Binary files skipped: {files_skipped_binary}")
    print()
    print("Top 20 files by replacement count:")
    for path, n in per_file[:20]:
        print(f"  {n:4d}  {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
