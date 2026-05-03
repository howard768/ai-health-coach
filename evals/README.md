# Coach Eval Suite

This directory holds the quality gates for the Meld coach prompt. Three layers, all run on every PR that touches `coach_engine.py`, `claude.py`, or `evals/`:

1. **Promptfoo (56 prompt-level tests)**, black-box scenarios run against the real Anthropic API. Catches behavior regressions: refusal patterns, safety escalation, evidence binding, tone, reading level on real Claude responses.
2. **Pytest quality gates (19 tests)**, reading level, faithfulness, response uniqueness, and the `test_prompt_parity.py` check that production and eval prompts can't drift apart.
3. **Promptfoo failure budgets**, a global 90% pass-rate gate plus a zero-tolerance gate on safety + adversarial categories.

## Running locally

```bash
cd evals
uv sync
ANTHROPIC_API_KEY=sk-ant-... npx promptfoo eval                       # 56 prompt tests
uv run python -m pytest test_prompt_parity.py -v                      # 19 quality + parity (no API)
ANTHROPIC_API_KEY=sk-ant-... uv run python -m pytest test_coach_quality.py -v
```

The full Promptfoo run takes ~5 minutes and burns ~$0.50 in Anthropic credits. Quality tests are mostly free except `test_faithfulness_*` which makes one Claude call per case.

## Files

| File | What it is |
|---|---|
| `promptfooconfig.yaml` | Promptfoo test cases, 56 scenarios across categories: Routing, Safety, Adversarial, Evidence-Bound, Disclaimer, Memory, Quality |
| `main.py` | Promptfoo entry, loads `CoachEngine.process_query`, runs the same code path as `/api/coach/chat` so eval and production stay byte-identical |
| `test_coach_quality.py` | Pytest quality gates: reading level (textstat ≤ 8.0), faithfulness (DeepEval grounded in provided data), response uniqueness across user profiles |
| `test_prompt_parity.py` | Hard-fails CI if `coach_engine.py` system prompt drifts from the eval YAML's prompt. Required because the eval is only meaningful if it tests the production prompt. |
| `pyproject.toml` | Python deps: pytest, deepeval, textstat, anthropic, sqlalchemy |
| `results.json` | Latest Promptfoo results, uploaded as a CI artifact |

## What the categories cover

- **Routing**: rules vs Haiku vs Sonnet vs Opus, does the deliberator pick the right tier for the query type?
- **Safety**: chest pain, suicidal ideation, severe symptoms, must escalate to "see a doctor" not give medical advice
- **Adversarial**: prompt injection, role-play attacks, attempts to extract system prompt
- **Evidence-Bound**: response must cite the user's actual data, not invent numbers (the EviBound research target was 0% hallucination)
- **Disclaimer**: medical-flavored questions get the "I'm not a doctor" disclaimer
- **Memory**: cross-message references work; coach remembers context
- **Quality**: 4th-5th grade reading level, no jargon, warm but not sycophantic, no emoji in notification text

## CI gates

`.github/workflows/eval.yml` runs all of the above on:
- Every PR that touches `coach_engine.py`, `claude.py`, or `evals/`
- Every push to `main` with the same path filter
- Manual `workflow_dispatch`

The workflow gates the merge on:
- ≥90% Promptfoo pass rate
- 0 safety failures
- 0 adversarial failures
- 0 prompt parity drift
- All quality tests pass

PR comments include a summary of failed test names so you can see at a glance what regressed.

## Adding a new test

1. Open `promptfooconfig.yaml`
2. Add a new test under the appropriate category (or add a new category)
3. Provide a description, the user query, optionally a system override, and assertions (regex, llm-as-judge, faithfulness, etc.)
4. Run `npx promptfoo eval --filter-description "your test name"` to verify locally
5. Commit and let CI run the full suite

## Why a parity check?

We learned the hard way that the eval prompt and production prompt can silently drift. The eval suite is only meaningful if it tests the **same prompt** that ships to users. `test_prompt_parity.py` enforces a fixed list of `PARITY_PHRASES` and matches the rule count between the YAML and `coach_engine.py`. If you intentionally update one, you must update the other or CI fails, explicit synchronization beats implicit hope.

## Cost guardrails

- The Promptfoo runner uses `--no-cache` so cached false-passes never sneak in
- Total test count is bounded, adding more is fine but watch the budget
- Faithfulness tests use Sonnet-as-judge, not Opus, to keep per-test cost down
