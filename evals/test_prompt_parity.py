"""Test that the eval prompt and the production coach prompt stay in sync.

The eval suite (`promptfooconfig.yaml`) defines a system prompt used to test
coach quality. The production coach engine (`backend/app/services/coach_engine.py`)
defines its own system prompt. These two have already drifted twice, once
when adding the magnesium fix, and again when adding the "trust current data"
rule.

This test enforces that both contain the same set of critical rules.

Run: cd evals && uv run python -m pytest test_prompt_parity.py -v
"""

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
EVAL_CONFIG = REPO_ROOT / "evals" / "promptfooconfig.yaml"
COACH_ENGINE = REPO_ROOT / "backend" / "app" / "services" / "coach_engine.py"


# Critical phrases that MUST appear in both prompts. If you change one,
# you must update the other (and add the change here).
PARITY_PHRASES = [
    "EVERY claim",
    "specific data point",
    "NEVER make up numbers",
    "4th grade reading level",
    "wellness coach, NOT a doctor",
    "NEVER recommend specific supplement dosages",
    "988",  # Crisis lifeline
    "741741",  # Crisis Text Line
    "Crisis Text Line",  # Second crisis resource
    "supplement questions",  # Rule 2 carve-out
    "general evidence-based knowledge",
]


@pytest.fixture(scope="module")
def eval_prompt() -> str:
    return EVAL_CONFIG.read_text()


@pytest.fixture(scope="module")
def production_prompt() -> str:
    return COACH_ENGINE.read_text()


@pytest.mark.parametrize("phrase", PARITY_PHRASES)
def test_eval_prompt_contains(eval_prompt: str, phrase: str):
    assert phrase in eval_prompt, (
        f"Eval config is missing the parity phrase: {phrase!r}\n"
        f"Update {EVAL_CONFIG.name} to match the production coach prompt."
    )


@pytest.mark.parametrize("phrase", PARITY_PHRASES)
def test_production_prompt_contains(production_prompt: str, phrase: str):
    assert phrase in production_prompt, (
        f"Production coach prompt is missing the parity phrase: {phrase!r}\n"
        f"Update {COACH_ENGINE.name} to match the eval suite."
    )


def test_rule_count_matches():
    """Both prompts should have the same number of numbered rules."""
    import re
    eval_text = EVAL_CONFIG.read_text()
    prod_text = COACH_ENGINE.read_text()

    # Match "1. ", "2. ", etc. at start of line in both
    eval_rules = set(re.findall(r"^\s*(\d+)\.\s", eval_text, re.MULTILINE))
    # Production coach has rules inside the EVIDENCE_BOUND_SYSTEM_PROMPT triple-string
    prod_rules = set(re.findall(r"^(\d+)\.\s", prod_text, re.MULTILINE))

    # Eval has many "1. ", "2. " from rules in YAML, extract just the prompt section
    # Look for the CRITICAL RULES block specifically
    eval_critical = re.search(
        r"CRITICAL RULES:(.*?)USER",
        eval_text,
        re.DOTALL,
    )
    if eval_critical:
        eval_rule_count = len(re.findall(r"^\s*(\d+)\.\s", eval_critical.group(1), re.MULTILINE))
    else:
        eval_rule_count = 0

    prod_critical = re.search(
        r"CRITICAL RULES:(.*?)\{safety_disclaimer\}",
        prod_text,
        re.DOTALL,
    )
    if prod_critical:
        prod_rule_count = len(re.findall(r"^(\d+)\.\s", prod_critical.group(1), re.MULTILINE))
    else:
        prod_rule_count = 0

    assert eval_rule_count > 0, "No rules found in eval prompt"
    assert prod_rule_count > 0, "No rules found in production prompt"
    assert eval_rule_count == prod_rule_count, (
        f"Rule count mismatch: eval has {eval_rule_count} rules, "
        f"production has {prod_rule_count}. Keep them in sync."
    )
