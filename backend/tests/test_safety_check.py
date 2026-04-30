"""Tests for `SafetyCheck.check_health_data` and
`SafetyCheck.check_message_content`.

These are CRITICAL safety gates flagged in the 2026-04-30 audit (MEL-43)
as zero-test:
  - `check_health_data` is the deterministic gate BEFORE any AI processing.
    Routes concerning biometrics to Opus and adds a disclaimer. Drift in
    the threshold logic = either spurious alerts or missed crisis routing.
  - `check_message_content` detects crisis language in user chat. False
    negatives = a user in distress gets a routine response. False positives
    = users get an unwanted disclaimer for benign messages.

Both are pure functions on a dataclass — easy to unit test without DB or
AI mocks.

Run: cd backend && uv run pytest tests/test_safety_check.py -v
"""

import os

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-safety-tests")

from app.services.coach_engine import SafetyCheck


# ── check_health_data: deterministic biometric gates ─────────────────────


def test_health_data_empty_dict_not_concerning():
    result = SafetyCheck.check_health_data({})
    assert result.is_concerning is False
    assert result.reasons == []
    assert result.requires_disclaimer is False
    assert result.requires_opus is False


def test_health_data_normal_values_not_concerning():
    """Healthy ranges must NOT trip safety routing."""
    result = SafetyCheck.check_health_data({
        "hrv_average": 55,
        "resting_hr": 65,
        "sleep_efficiency": 88,
        "readiness_score": 75,
    })
    assert result.is_concerning is False


def test_health_data_hrv_critically_low_concerning():
    """HRV < 20ms suggests autonomic dysfunction → requires Opus + disclaimer."""
    result = SafetyCheck.check_health_data({"hrv_average": 15})
    assert result.is_concerning is True
    assert result.requires_disclaimer is True
    assert result.requires_opus is True
    assert any("HRV" in r for r in result.reasons)


def test_health_data_hrv_at_boundary_20_not_concerning():
    """20ms is the cutoff (< 20 triggers); == 20 must NOT trigger."""
    result = SafetyCheck.check_health_data({"hrv_average": 20})
    # Boundary: per the implementation, condition is `hrv < 20`, so 20 is fine.
    assert result.is_concerning is False or "HRV" not in (result.reasons[0] if result.reasons else "")


def test_health_data_resting_hr_elevated_concerning():
    """RHR > 100 bpm at rest is tachycardia."""
    result = SafetyCheck.check_health_data({"resting_hr": 110})
    assert result.is_concerning is True
    assert any("Resting HR" in r for r in result.reasons)


def test_health_data_sleep_efficiency_critically_low():
    result = SafetyCheck.check_health_data({"sleep_efficiency": 40})
    assert result.is_concerning is True
    assert any("Sleep efficiency" in r for r in result.reasons)


def test_health_data_readiness_critically_low():
    result = SafetyCheck.check_health_data({"readiness_score": 15})
    assert result.is_concerning is True
    assert any("Readiness" in r for r in result.reasons)


def test_health_data_hrv_baseline_deviation_with_history():
    """30% deviation from a real baseline (≥3 days history) triggers."""
    result = SafetyCheck.check_health_data({
        "hrv_average": 30,
        "baseline_hrv": 50,  # 40% deviation
        "baseline_days": 7,
    })
    assert result.is_concerning is True
    assert any("baseline" in r for r in result.reasons)


def test_health_data_baseline_deviation_skipped_with_thin_history():
    """Need ≥ 3 days of baseline; thinner history must NOT trigger."""
    result = SafetyCheck.check_health_data({
        "hrv_average": 30,
        "baseline_hrv": 50,  # would trigger
        "baseline_days": 2,  # but baseline is too thin
    })
    # Should not flag as concerning solely due to baseline deviation
    assert all("baseline" not in r for r in result.reasons)


def test_health_data_multiple_concerns_all_recorded():
    """If multiple metrics trip, all reasons are listed."""
    result = SafetyCheck.check_health_data({
        "hrv_average": 15,
        "resting_hr": 110,
        "readiness_score": 15,
    })
    assert result.is_concerning is True
    assert len(result.reasons) >= 3


def test_health_data_none_values_dont_trigger():
    """Missing data (None) must not falsely trigger any gate."""
    result = SafetyCheck.check_health_data({
        "hrv_average": None,
        "resting_hr": None,
        "sleep_efficiency": None,
        "readiness_score": None,
    })
    assert result.is_concerning is False


# ── check_message_content: crisis-language gate ──────────────────────────


def test_message_content_benign_text_not_concerning():
    """Benign messages must NOT route to Opus."""
    result = SafetyCheck.check_message_content("How was my sleep last night?")
    assert result.is_concerning is False
    assert result.requires_opus is False
    assert result.reasons == []


def test_message_content_routine_negative_emotion_not_crisis():
    """Frustration / sadness without crisis language is NOT flagged."""
    result = SafetyCheck.check_message_content("I'm really tired and grumpy today.")
    assert result.is_concerning is False


def test_message_content_explicit_suicide_concerning():
    result = SafetyCheck.check_message_content("Sometimes I think about suicide.")
    assert result.is_concerning is True
    assert result.requires_opus is True
    assert any("Crisis language" in r for r in result.reasons)


def test_message_content_self_harm_concerning():
    result = SafetyCheck.check_message_content("I want to hurt myself.")
    assert result.is_concerning is True


def test_message_content_indirect_phrase_concerning():
    """The phrase list covers 'better off without me' style indirect language."""
    result = SafetyCheck.check_message_content(
        "Lately I feel like everyone would be better off without me."
    )
    assert result.is_concerning is True


def test_message_content_case_insensitive():
    """Detection must be case-insensitive (text_lower in implementation)."""
    result = SafetyCheck.check_message_content("I want to KILL MYSELF tonight.")
    assert result.is_concerning is True


def test_message_content_apostrophe_variants_both_caught():
    """Both 'don't' and 'dont' (no apostrophe) variants must trip."""
    a = SafetyCheck.check_message_content("I don't want to be here anymore.")
    b = SafetyCheck.check_message_content("I dont want to be here anymore.")
    assert a.is_concerning is True
    assert b.is_concerning is True


def test_message_content_does_not_set_disclaimer_flag():
    """Crisis language routes to Opus but does NOT add the health-metric
    disclaimer (the prompt's Rule 8 handles the response tone)."""
    result = SafetyCheck.check_message_content("I want to end my life.")
    assert result.requires_opus is True
    assert result.requires_disclaimer is False
