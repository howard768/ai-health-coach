"""Claude Haiku dual-agent coach-chat simulator for Phase 4.5.

Produces synthetic coach conversations that Phase 5.9 Promptfoo
active-patterns cases can consume as fixtures. Two agents, a user
persona and the coach, take turns responding to each other. Either
agent may be backed by a live LLM or by the deterministic template
fallback (the default). The ``llm_callable`` parameter lets a test
inject a stub without monkeypatching anything.

Non-negotiable invariants pinned by the test suite:

1. **Voice compliance on every string.** Every response passes
   ``voice_compliance.check_all`` before it lands in a
   ``ConversationTurn``. On an em-dash-only failure we scrub and re-
   check; on anything else we fall back to the persona template.
2. **Adversarial share matches the configured fraction.** Over a
   cohort, the share of adversarial-persona conversations sits within
   a few percent of ``adversarial_fraction`` (verified via a binomial
   tolerance band in the test).
3. **``is_synthetic=True`` on every fragment.** The factory does not
   write these rows to the database (Commit 4 has no conversations
   table); the flag travels on the in-memory dataclass so fixture
   writers and any future DB writer stay honest.
4. **Deterministic with seed.** Same demographics + seed +
   llm_callable produces identical output across runs.

Nothing in this module imports anthropic at module load. When a caller
wants real Haiku, they construct an LLM callable and pass it in;
``_make_haiku_callable`` is provided as a helper, and imports
anthropic lazy-inside.
"""

from __future__ import annotations

import json
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from ml.narrate.voice_compliance import check_all, scrub_em_dashes
from ml.synth.demographics import Demographics


# (system_prompt, messages) -> text. messages use the standard Anthropic
# shape: ``{"role": "user"|"assistant", "content": str}``.
LLMCallable = Callable[[str, list[dict]], str]


_PERSONAS_PATH = Path(__file__).resolve().parent / "fixtures" / "personas.json"

# Lightweight module-level cache. Personas.json is a few KB; caching
# keeps repeated cohort generations free of file-system hits in tight
# loops (e.g. the fidelity test suite in Commit 7 will call
# ``generate_cohort`` many times).
_PERSONAS_CACHE: list[dict] | None = None


@dataclass(frozen=True)
class ConversationTurn:
    """One message in a synthetic conversation.

    ``role`` is ``"user"`` or ``"coach"``. Matches the schema of the
    real ``ChatMessageRecord`` so a future commit can persist fragments
    without shape rewrites.
    """

    role: str
    content: str


@dataclass
class ConversationFragment:
    """A whole synthetic conversation for one synth user.

    ``is_synthetic=True`` is pinned via the default. If a caller ever
    constructs a fragment by hand, flipping this flag is the explicit
    act of saying "this is not synth data", which is exactly the audit
    boundary we want to preserve.
    """

    user_id: str
    persona: str
    is_adversarial: bool
    turns: list[ConversationTurn] = field(default_factory=list)
    is_synthetic: bool = True


# ─────────────────────────────────────────────────────────────────────────
# Persona loading
# ─────────────────────────────────────────────────────────────────────────


def _load_personas() -> list[dict]:
    """Load personas from the JSON fixture. Cached at module level."""
    global _PERSONAS_CACHE
    if _PERSONAS_CACHE is not None:
        return _PERSONAS_CACHE
    data = json.loads(_PERSONAS_PATH.read_text(encoding="utf-8"))
    personas = data.get("personas", [])
    if not personas:
        raise RuntimeError("personas.json loaded with an empty personas list")
    _PERSONAS_CACHE = personas
    return personas


# ─────────────────────────────────────────────────────────────────────────
# Voice enforcement
# ─────────────────────────────────────────────────────────────────────────


def _voice_enforce(text: str, fallback: str) -> str:
    """Return ``text`` when it passes voice rules, otherwise the fallback.

    Mirrors the translator.py pattern: one em-dash scrub retry, then
    fallback. Any non-em-dash failure (emoji, grade level) goes
    straight to fallback; nothing we could do mechanically fixes those.
    """
    result = check_all(text)
    if result.passed:
        return text
    if result.em_dash:
        scrubbed = scrub_em_dashes(text)
        if check_all(scrubbed).passed:
            return scrubbed
    return fallback


# ─────────────────────────────────────────────────────────────────────────
# Default LLM callable (deterministic template-backed)
# ─────────────────────────────────────────────────────────────────────────


def _make_default_llm(personas: list[dict]) -> LLMCallable:
    """Build a templated LLM callable. Deterministic, zero-cost.

    Looks up the persona the caller intends by comparing the system
    prompt against the two prompts (coach, user) stored on each
    persona. Returns the pool entry at index ``len(messages) % N``, so
    successive turns walk through the pool deterministically.
    """
    coach_prompts = {p["coach_system_prompt"]: p for p in personas}
    user_prompts = {p["user_system_prompt"]: p for p in personas}

    def call(system: str, messages: list[dict]) -> str:
        if system in coach_prompts:
            p = coach_prompts[system]
            pool = p["archetype_coach_templates"]
        elif system in user_prompts:
            p = user_prompts[system]
            pool = p["archetype_openers"]
        else:
            return "Noted. Keep logging, and we will revisit tomorrow."
        idx = len(messages) % len(pool)
        return pool[idx]

    return call


def _make_haiku_callable() -> LLMCallable:
    """Build a Haiku-backed callable. Lazy-imports the Anthropic SDK.

    Not wired in by default because Commit 4 tests must stay zero-cost.
    Phase 5.9 (or any caller that wants real dialogue variety) imports
    this, constructs the callable, and passes it through to
    ``generate_conversations``.
    """

    def call(system: str, messages: list[dict]) -> str:
        # Lazy imports; keeps the conversations module cold-boot safe
        # even when a caller never uses the Haiku path.
        import anthropic

        from app.config import settings

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            system=system,
            max_tokens=400,
            messages=messages,  # type: ignore[arg-type]
        )
        blocks = getattr(response, "content", []) or []
        for block in blocks:
            text = getattr(block, "text", None)
            if text:
                return text.strip()
        return ""

    return call


# ─────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────


def generate_conversations(
    demographics: list[Demographics],
    adversarial_fraction: float = 0.20,
    seed: int | None = None,
    turns_per_conversation: int = 4,
    llm_callable: LLMCallable | None = None,
) -> list[ConversationFragment]:
    """Produce one ``ConversationFragment`` per synth user.

    ``turns_per_conversation`` counts message turns after the opener
    (so total messages = opener + turns). With the default of 4, each
    conversation has 5 messages: opener + coach + user + coach + user.

    Every string lands through ``_voice_enforce`` so fragments that
    reach the caller are guaranteed to pass voice rules.
    """
    if not 0.0 <= adversarial_fraction <= 1.0:
        raise ValueError(
            f"adversarial_fraction must be in [0, 1], got {adversarial_fraction}"
        )
    if turns_per_conversation < 0:
        raise ValueError(
            f"turns_per_conversation must be >= 0, got {turns_per_conversation}"
        )

    personas = _load_personas()
    adversarial_pool = [p for p in personas if p.get("adversarial")]
    regular_pool = [p for p in personas if not p.get("adversarial")]
    if not adversarial_pool or not regular_pool:
        raise RuntimeError(
            "personas.json must define at least one adversarial and one regular persona"
        )

    rng = random.Random(seed)
    llm = llm_callable or _make_default_llm(personas)

    out: list[ConversationFragment] = []
    for demo in demographics:
        is_adversarial = rng.random() < adversarial_fraction
        pool = adversarial_pool if is_adversarial else regular_pool
        persona = rng.choice(pool)

        # Seed with a persona opener (from the user side). The opener
        # is a deterministic choice so the same demo + seed sequence
        # produces the same conversation.
        opener = rng.choice(persona["archetype_openers"])
        fallback_user = persona["archetype_openers"][0]
        opener_text = _voice_enforce(opener, fallback_user)

        fragment = ConversationFragment(
            user_id=demo.user_id,
            persona=persona["name"],
            is_adversarial=is_adversarial,
            turns=[ConversationTurn(role="user", content=opener_text)],
        )

        # Alternate coach, user, coach, user ... for the requested
        # number of follow-up turns.
        for turn_idx in range(turns_per_conversation):
            if turn_idx % 2 == 0:
                # Coach turn.
                messages_for_llm = [
                    {
                        "role": "user" if t.role == "user" else "assistant",
                        "content": t.content,
                    }
                    for t in fragment.turns
                ]
                raw = llm(persona["coach_system_prompt"], messages_for_llm)
                fallback_coach = persona["archetype_coach_templates"][0]
                text = _voice_enforce(raw, fallback_coach)
                fragment.turns.append(ConversationTurn(role="coach", content=text))
            else:
                # User follow-up turn. Keep it short by templating off
                # the opener pool; the default llm_callable already
                # picks a different index each turn.
                messages_for_llm = [
                    {
                        "role": "assistant" if t.role == "coach" else "user",
                        "content": t.content,
                    }
                    for t in fragment.turns
                ]
                raw = llm(persona["user_system_prompt"], messages_for_llm)
                text = _voice_enforce(raw, fallback_user)
                fragment.turns.append(ConversationTurn(role="user", content=text))

        out.append(fragment)

    return out


__all__ = [
    "ConversationFragment",
    "ConversationTurn",
    "LLMCallable",
    "generate_conversations",
]
