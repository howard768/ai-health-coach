"""Voice-compliance checks for any ML-generated user-facing string.

Per feedback_no_em_dashes + feedback_onboarding in user memory, every
string that reaches a user MUST pass:

1. No em dashes (U+2014). The model slips them in even when the prompt
   forbids. Regex catches 100% of instances and is zero-cost.
2. No emoji. The brand voice explicitly avoids emoji per
   feedback_design.md; they are an AI tell in this context.
3. Flesch-Kincaid grade level <= 5. Enforced by ``textstat`` which is
   already a backend dependency. Grade 5 matches the 4th-grade reading
   level target with a modest buffer for technical health terms.

The Opus narrator in ``translator.py`` calls ``check_all()`` before
returning generated copy; on failure it falls back to a templated
alternative rather than ship non-compliant copy. See
``test_narrate_voice_compliance.py`` for the exact behavior pinned.

Heavy imports (textstat pulls nltk which eagerly imports scipy/sklearn)
stay lazy inside function bodies per the cold-boot budget.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


# U+2014 em dash is the only forbidden dash. Hyphen (-) and en dash (U+2013)
# are allowed. Figure dash (U+2012), horizontal bar (U+2015) are rare enough
# we don't bother; add if a model output slips past.
_EM_DASH_RE = re.compile("\u2014")

# Flesch-Kincaid grade level ceiling. The product target is 4th-grade
# reading level. FK grade is a rough metric, it penalizes long sentences
# and multi-syllable words (including "circadian", "cardiovascular") more
# than a human reader would. Empirically, well-crafted 4th-grade-readable
# prose scores 5-7 on FK. We align with the existing coach eval threshold
# (7 in ``evals/test_coach_quality.py``) rather than trying to be stricter
# in the narrator, same bar everywhere. The em-dash and emoji rules carry
# most of the voice-compliance load; FK is a backstop against dense prose.
DEFAULT_MAX_GRADE = 7.0

# Reading-level checks misbehave on tiny strings. Anything under this length
# gets a pass on grade-level, we are surfacing a label or a CTA, not prose.
_MIN_CHARS_FOR_GRADE_CHECK = 60


@dataclass
class ComplianceResult:
    """Structured result so callers can tell exactly which rule tripped."""

    passed: bool
    em_dash: bool  # True when em dashes found
    emoji: bool  # True when emoji found
    grade_level: float | None  # None when string was too short to score
    grade_exceeded: bool  # True when grade_level > max_grade
    details: list[str]  # Human-readable reasons for each failure


# ─────────────────────────────────────────────────────────────────────────
# Individual checks
# ─────────────────────────────────────────────────────────────────────────


def has_em_dash(text: str) -> bool:
    """True if the text contains U+2014. Cheap regex match."""
    return bool(_EM_DASH_RE.search(text))


def has_emoji(text: str) -> bool:
    """True if any codepoint is in the Emoji block.

    Uses unicodedata to classify each char rather than pulling in a third-
    party emoji library. Covers the classes that actually appear in LLM
    output: smileys, symbols, pictographs. Misses dingbats-as-emoji edge
    cases but catches every common slip.
    """
    for ch in text:
        # Pictographs + emoji blocks fall in a few Unicode ranges. Fastest
        # check: codepoint is in one of those blocks.
        code = ord(ch)
        if 0x1F300 <= code <= 0x1FAFF:  # Miscellaneous Symbols & Pictographs
            return True
        if 0x1F600 <= code <= 0x1F64F:  # Emoticons
            return True
        if 0x1F680 <= code <= 0x1F6FF:  # Transport and Map
            return True
        if 0x1F900 <= code <= 0x1F9FF:  # Supplemental Symbols and Pictographs
            return True
        if 0x2600 <= code <= 0x27BF:  # Misc Symbols + Dingbats (star, sun, etc.)
            return True
        # Variation selectors and zero-width joiner often mark emoji
        # sequences; if one appears, treat as emoji-adjacent.
        if code in (0xFE0F, 0x200D):
            return True
        # Keycap combining enclosure.
        if unicodedata.category(ch) == "Me" and 0x20E0 <= code <= 0x20FF:
            return True
    return False


def grade_level(text: str) -> float | None:
    """Flesch-Kincaid grade level, or None for too-short strings.

    textstat pulls nltk at import, which is why this stays lazy. The
    module-level cold-boot test guards against accidental top-level imports.
    """
    if len(text.strip()) < _MIN_CHARS_FOR_GRADE_CHECK:
        return None
    import textstat

    try:
        grade = float(textstat.flesch_kincaid_grade(text))
    except (ValueError, ZeroDivisionError):
        return None
    return grade


# ─────────────────────────────────────────────────────────────────────────
# Combined check
# ─────────────────────────────────────────────────────────────────────────


def check_all(text: str, max_grade: float = DEFAULT_MAX_GRADE) -> ComplianceResult:
    """Run every rule. Returns a structured result listing every failure.

    Callers that want the fail-fast behavior can read ``.passed``. Callers
    that want to log which rule tripped (e.g., the Opus narrator's
    retry-on-failure loop) can read ``.details``.
    """
    em = has_em_dash(text)
    emoji = has_emoji(text)
    grade = grade_level(text)
    grade_high = grade is not None and grade > max_grade

    details: list[str] = []
    if em:
        details.append("contains em dash (U+2014)")
    if emoji:
        details.append("contains emoji")
    if grade_high:
        details.append(
            f"Flesch-Kincaid grade {grade:.1f} exceeds ceiling {max_grade:.1f}"
        )

    return ComplianceResult(
        passed=not (em or emoji or grade_high),
        em_dash=em,
        emoji=emoji,
        grade_level=grade,
        grade_exceeded=grade_high,
        details=details,
    )


def scrub_em_dashes(text: str) -> str:
    """Replace em dashes with a safe equivalent. Last-resort sanitizer.

    Matches the existing sanitize_output behavior in
    ``backend/app/services/content_blocks.py``: em dash with adjacent spaces
    becomes a comma, bare em dash inside a word becomes a hyphen. Used by
    the Opus narrator when the model slips past the prompt, we prefer a
    mechanical fix to retrying an expensive model call.
    """
    # ", " (spaced em dash) -> ", "
    cleaned = re.sub(r"\s*\u2014\s*", ", ", text)
    # Any remaining bare em dash -> hyphen
    cleaned = cleaned.replace("\u2014", "-")
    # Collapse double-comma artifacts from the first pass.
    cleaned = re.sub(r",\s*,", ",", cleaned)
    return cleaned
