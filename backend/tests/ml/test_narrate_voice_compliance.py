"""Voice compliance checker tests, pure Python, no DB, no LLM.

Voice is non-negotiable per feedback_no_em_dashes + feedback_onboarding.
Every ML-generated user-facing string must pass these rules before it
ships. The Opus narrator uses ``check_all`` as a gate; this suite pins
the behavior so a future refactor can't quietly loosen the bar.

Run: ``cd backend && uv run python -m pytest tests/ml/test_narrate_voice_compliance.py -v``
"""

from __future__ import annotations

import pytest

from ml.narrate import voice_compliance


# ─────────────────────────────────────────────────────────────────────────
# has_em_dash
# ─────────────────────────────────────────────────────────────────────────


def test_em_dash_detected():
    assert voice_compliance.has_em_dash("A sentence \u2014 with an em dash.") is True


def test_regular_hyphen_is_fine():
    assert voice_compliance.has_em_dash("A 7-day average is not a problem.") is False


def test_en_dash_is_allowed():
    # U+2013 is an en dash, plan allows it. Only U+2014 is forbidden.
    assert voice_compliance.has_em_dash("Range 40\u201350 bpm.") is False


def test_multiple_em_dashes_detected():
    assert voice_compliance.has_em_dash("A \u2014 B \u2014 C") is True


# ─────────────────────────────────────────────────────────────────────────
# has_emoji
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text",
    [
        "Great job! \U0001F44D",  # thumbs up
        "Your sleep was solid \U0001F634",  # sleeping face
        "\u2600 sunny day",  # sun (in misc symbols range)
        "Running \U0001F3C3 today",  # runner
    ],
)
def test_emoji_detected_across_ranges(text):
    assert voice_compliance.has_emoji(text) is True


def test_plain_text_has_no_emoji():
    assert voice_compliance.has_emoji("Your HRV was 42 ms last night.") is False


def test_ascii_punctuation_is_not_emoji():
    assert voice_compliance.has_emoji("Sleep score: 85% (up from 78%).") is False


# ─────────────────────────────────────────────────────────────────────────
# grade_level
# ─────────────────────────────────────────────────────────────────────────


def test_short_strings_skip_grade_check():
    # textstat is unreliable on tiny strings. Plan is to give them a pass.
    assert voice_compliance.grade_level("Hi.") is None


def test_simple_prose_scores_low_grade():
    # 4th-grade-ish prose should score under the ceiling (6.0). FK is a rough
    # metric, real 4th-grade-readable prose often scores 5-7 on FK.
    text = (
        "Your sleep was good last night. You got seven hours in bed. "
        "Your heart rate was steady. Keep up the good work today."
    )
    grade = voice_compliance.grade_level(text)
    assert grade is not None
    assert grade <= voice_compliance.DEFAULT_MAX_GRADE


def test_dense_prose_scores_high_grade():
    # Deliberately long words + long sentences push the grade up.
    text = (
        "Heterogeneous autonomic variability patterns, particularly those "
        "involving parasympathetic modulation throughout nocturnal recovery "
        "periods, demonstrate measurable associations with subsequent "
        "cardiovascular homeostasis in longitudinally tracked populations."
    )
    grade = voice_compliance.grade_level(text)
    assert grade is not None
    assert grade > voice_compliance.DEFAULT_MAX_GRADE


# ─────────────────────────────────────────────────────────────────────────
# check_all
# ─────────────────────────────────────────────────────────────────────────


def test_check_all_passes_on_clean_simple_text():
    text = (
        "Your sleep was solid last night. You got eight hours in bed. "
        "Your heart rate was steady. Go rest up today."
    )
    result = voice_compliance.check_all(text)
    assert result.passed is True
    assert result.em_dash is False
    assert result.emoji is False
    assert result.details == []


def test_check_all_flags_em_dash():
    text = (
        "Your sleep was solid \u2014 eight hours in bed. Your heart rate was steady. "
        "Rest up today."
    )
    result = voice_compliance.check_all(text)
    assert result.passed is False
    assert result.em_dash is True
    assert "em dash" in result.details[0]


def test_check_all_flags_emoji():
    text = (
        "Your sleep was solid \U0001F44D eight hours in bed. Your heart rate was steady. "
        "Rest up today."
    )
    result = voice_compliance.check_all(text)
    assert result.passed is False
    assert result.emoji is True


def test_check_all_flags_high_grade():
    text = (
        "Heterogeneous autonomic variability patterns, particularly those "
        "involving parasympathetic modulation throughout nocturnal recovery "
        "periods, demonstrate measurable associations with subsequent "
        "cardiovascular homeostasis in longitudinally tracked populations."
    )
    result = voice_compliance.check_all(text)
    assert result.grade_exceeded is True
    assert result.passed is False


def test_check_all_stacks_multiple_failures():
    text = (
        "Heterogeneous autonomic variability patterns \u2014 involving "
        "parasympathetic modulation \U0001F634 throughout nocturnal recovery, "
        "demonstrate measurable associations with cardiovascular homeostasis."
    )
    result = voice_compliance.check_all(text)
    assert result.passed is False
    assert result.em_dash is True
    assert result.emoji is True
    assert len(result.details) >= 2


# ─────────────────────────────────────────────────────────────────────────
# scrub_em_dashes
# ─────────────────────────────────────────────────────────────────────────


def test_scrub_em_dashes_handles_spaced_em_dash():
    text = "Your sleep was solid \u2014 eight hours in bed."
    assert "\u2014" not in voice_compliance.scrub_em_dashes(text)
    assert ", " in voice_compliance.scrub_em_dashes(text)


def test_scrub_em_dashes_handles_bare_em_dash():
    text = "7\u201410 range"
    scrubbed = voice_compliance.scrub_em_dashes(text)
    assert "\u2014" not in scrubbed


def test_scrub_em_dashes_preserves_clean_text():
    text = "Your sleep was solid. Eight hours in bed."
    assert voice_compliance.scrub_em_dashes(text) == text


def test_scrub_em_dashes_collapses_double_commas():
    text = "Your sleep \u2014 , was solid"
    scrubbed = voice_compliance.scrub_em_dashes(text)
    assert ", ," not in scrubbed
