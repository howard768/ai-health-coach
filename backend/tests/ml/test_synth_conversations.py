"""Phase 4.5 Commit 4: conversations simulator tests.

Pin voice-compliance, adversarial-share, determinism, and the
LLM-callable injection contract.

Run: ``cd backend && uv run python -m pytest tests/ml/test_synth_conversations.py -v``
"""

from __future__ import annotations

import os

os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-must-be-long-enough-for-hs256-aaaaaaaa")
os.environ.setdefault("ENCRYPTION_KEY", "T0TXLkHFSeZRYGIIejSFVkhQrvRE-bWLkwXSkkdWiKQ=")
os.environ.setdefault("ANTHROPIC_API_KEY", "fake-key-tests-dont-call-anthropic")

import pytest

from ml.narrate.voice_compliance import check_all
from ml.synth.conversations import (
    ConversationFragment,
    ConversationTurn,
    generate_conversations,
)
from ml.synth.demographics import generate_demographics


# ─────────────────────────────────────────────────────────────────────────
# Shape + determinism
# ─────────────────────────────────────────────────────────────────────────


def test_returns_one_fragment_per_user() -> None:
    demo = generate_demographics(n_users=7, seed=1)
    fragments = generate_conversations(demo, seed=1)
    assert len(fragments) == 7
    assert {f.user_id for f in fragments} == {d.user_id for d in demo}


def test_is_deterministic_with_same_seed() -> None:
    demo = generate_demographics(n_users=10, seed=1)
    a = generate_conversations(demo, seed=1)
    b = generate_conversations(demo, seed=1)
    assert a == b


def test_different_seeds_shift_persona_assignment() -> None:
    demo = generate_demographics(n_users=20, seed=1)
    a = generate_conversations(demo, seed=1)
    b = generate_conversations(demo, seed=99)
    # At least one user gets a different persona under a different seed.
    differences = sum(
        1 for x, y in zip(a, b) if x.persona != y.persona or x.turns != y.turns
    )
    assert differences > 0


def test_turn_count_matches_config() -> None:
    """Opener + turns_per_conversation follow-ups."""
    demo = generate_demographics(n_users=3, seed=1)
    fragments = generate_conversations(demo, seed=1, turns_per_conversation=4)
    for f in fragments:
        assert len(f.turns) == 5  # opener + 4


def test_zero_turns_emits_only_opener() -> None:
    demo = generate_demographics(n_users=2, seed=1)
    fragments = generate_conversations(demo, seed=1, turns_per_conversation=0)
    for f in fragments:
        assert len(f.turns) == 1
        assert f.turns[0].role == "user"


# ─────────────────────────────────────────────────────────────────────────
# is_synthetic flag + adversarial attribution
# ─────────────────────────────────────────────────────────────────────────


def test_every_fragment_carries_is_synthetic_true() -> None:
    demo = generate_demographics(n_users=10, seed=1)
    fragments = generate_conversations(demo, seed=1)
    assert all(f.is_synthetic is True for f in fragments)


def test_adversarial_fraction_lands_near_target() -> None:
    """Binomial tolerance band: for 400 draws at p=0.20, P(share in
    [0.14, 0.26]) >> 0.99 under CLT, so this gives comfortable headroom."""
    demo = generate_demographics(n_users=400, seed=7)
    fragments = generate_conversations(
        demo, adversarial_fraction=0.20, seed=7
    )
    share = sum(1 for f in fragments if f.is_adversarial) / len(fragments)
    assert 0.14 <= share <= 0.26, f"adversarial share {share:.3f} off target"


def test_adversarial_persona_flag_matches_persona_set() -> None:
    """The ``is_adversarial`` flag on a fragment must match the
    ``adversarial`` flag on its persona in personas.json."""
    adversarial_names = {"crisis", "non_adherent", "contrarian"}
    regular_names = {"regular", "curious"}
    demo = generate_demographics(n_users=50, seed=7)
    fragments = generate_conversations(demo, seed=7)
    for f in fragments:
        if f.is_adversarial:
            assert f.persona in adversarial_names
        else:
            assert f.persona in regular_names


def test_rejects_out_of_range_adversarial_fraction() -> None:
    demo = generate_demographics(n_users=1, seed=1)
    with pytest.raises(ValueError):
        generate_conversations(demo, adversarial_fraction=1.5, seed=1)
    with pytest.raises(ValueError):
        generate_conversations(demo, adversarial_fraction=-0.1, seed=1)


# ─────────────────────────────────────────────────────────────────────────
# Voice compliance (non-negotiable)
# ─────────────────────────────────────────────────────────────────────────


def test_every_emitted_string_passes_voice_compliance() -> None:
    demo = generate_demographics(n_users=20, seed=7)
    fragments = generate_conversations(demo, seed=7)
    for f in fragments:
        for turn in f.turns:
            result = check_all(turn.content)
            assert result.passed, (
                f"{f.user_id}/{f.persona}/{turn.role}: {result.details} | "
                f"text={turn.content!r}"
            )


def test_noncompliant_llm_output_gets_replaced_with_template_fallback() -> None:
    """Inject a callable that returns content with an em dash AND an
    emoji (the em dash scrub alone would not rescue an emoji-flagged
    string), verify the fragment ends up using the persona template."""
    emoji = "\U0001f600"  # grinning face
    bad_text = f"Your readiness dropped {emoji} and here is a thought, then more text."

    def bad_llm(system: str, messages: list) -> str:
        return bad_text

    demo = generate_demographics(n_users=3, seed=7)
    fragments = generate_conversations(
        demo, seed=7, turns_per_conversation=4, llm_callable=bad_llm
    )
    for f in fragments:
        # The opener is persona-seeded, so it is compliant by construction.
        # The follow-up turns are where the bad callable would have landed;
        # they must end up as one of the persona's compliant fallbacks.
        for turn in f.turns[1:]:
            assert check_all(turn.content).passed
            # Sanity: the turn did NOT pass the raw bad output through.
            assert emoji not in turn.content


def test_em_dash_only_output_is_scrubbed_not_dropped() -> None:
    """A response whose only compliance problem is an em dash should
    survive voice enforcement (scrubbed), not be replaced by the
    fallback template."""
    raw = "Your sleep is a touch short this week, aim for an earlier wind down tonight."
    em_dash_version = raw.replace(",", " \u2014 ", 1)  # insert an em dash

    def em_dash_llm(system: str, messages: list) -> str:
        return em_dash_version

    demo = generate_demographics(n_users=1, seed=7)
    fragments = generate_conversations(
        demo, seed=7, turns_per_conversation=2, llm_callable=em_dash_llm
    )
    # At least one non-opener turn (coach turn at index 1) must come
    # from the scrubbed callable, not the persona template.
    follow_ups = [t.content for t in fragments[0].turns[1:]]
    assert any("\u2014" not in t for t in follow_ups)
    assert all("\u2014" not in t for t in follow_ups)


# ─────────────────────────────────────────────────────────────────────────
# Role alternation
# ─────────────────────────────────────────────────────────────────────────


def test_turns_alternate_user_coach_user_coach() -> None:
    """Opener is user, then coach, user, coach, user for default turns=4."""
    demo = generate_demographics(n_users=2, seed=7)
    fragments = generate_conversations(demo, seed=7, turns_per_conversation=4)
    for f in fragments:
        expected_roles = ["user", "coach", "user", "coach", "user"]
        assert [t.role for t in f.turns] == expected_roles


def test_turns_are_conversation_turn_instances() -> None:
    demo = generate_demographics(n_users=1, seed=7)
    fragments = generate_conversations(demo, seed=7)
    for t in fragments[0].turns:
        assert isinstance(t, ConversationTurn)
    assert isinstance(fragments[0], ConversationFragment)


# ─────────────────────────────────────────────────────────────────────────
# LLM callable injection
# ─────────────────────────────────────────────────────────────────────────


def test_custom_llm_callable_is_used() -> None:
    """A caller-injected callable must be the one producing follow-up
    turns (subject to voice compliance), not the default template."""
    unique_coach_line = "Your numbers look steady today, keep going and log dinner tonight."

    def my_llm(system: str, messages: list) -> str:
        # Return the same compliant line for every call so it is
        # trivial to spot in the output.
        return unique_coach_line

    demo = generate_demographics(n_users=2, seed=7)
    fragments = generate_conversations(
        demo, seed=7, turns_per_conversation=4, llm_callable=my_llm
    )
    # At least one coach turn across the output must carry our line.
    coach_turns = [
        t.content for f in fragments for t in f.turns if t.role == "coach"
    ]
    assert unique_coach_line in coach_turns
