# keep_oracle

Drop-in Python module implementing the 3-stage Keep settlement stack from `../FINDINGS.md`.

## Quick start

```python
from keep_oracle import Oracle

oracle = Oracle()

verdict = oracle.settle(
    commitment="Hit recovery score 70+ on 5 days this week",
    window={"start": "2026-04-13T00:00:00Z", "end": "2026-04-19T23:59:59Z"},
    provider="whoop",   # or "oura"
    data=whoop_json,    # raw API response
)

if verdict.outcome == "settled_hit":
    pay_winning_side(verdict)
elif verdict.outcome == "settled_miss":
    pay_losing_side(verdict)
else:
    enqueue_for_human_review(verdict.reason)
```

`verdict.outcome` is always one of `settled_hit | settled_miss | pause_for_review`.

## What happens under the hood

1. **Deterministic gate** (`keep_oracle/gate.py`). Rule-based, no LLM. Checks:
   - Every record has `scoring_state == "SCORED"`
   - No missing days in the window (every date has ≥1 record)
   - No duplicate `cycle_id`s
   - `wearable_time_seconds > 64800` on cycles that affect the count
   - No null metrics on SCORED records
   - Commitment matches a whitelist template id (if `allowed_commitment_templates` passed)

   Any failure → `pause_for_review`, no LLM cost incurred. This catches cases 04 (missing day), 13 (dup cycles), 14 (pending scoring) in ~1ms deterministically.

2. **Primary oracle**: Opus 4.7 with the strict prompt. Chosen because in the overnight eval it had the highest reasoning quality (judge 8.9), 97% self-consistency, and the fewest over-cautious errors (3/29).

3. **Confirmation oracle**: Gemini 2.5 Pro with the strict prompt. Chosen because it's a different provider (uncorrelated failure modes) and 12× cheaper than Opus.

4. **Verdict gate**:
   - Both agree on `hit`/`miss` → settle
   - Disagreement OR either returns `ambiguous` → `pause_for_review`

Cost per settlement: ~$0.05. See `../FINDINGS.md` for the empirical basis.

## Customization

Swap models by passing callables to the constructor:

```python
from keep_oracle import Oracle
from keep_oracle.oracle import _call_anthropic, _call_gemini

# Use Sonnet as primary instead of Opus
oracle = Oracle(
    primary_fn=lambda c, w, p, d: _call_anthropic("claude-sonnet-4-6", c, w, p, d),
    confirmation_fn=lambda c, w, p, d: _call_gemini(c, w, p, d),
)
```

Use a commitment template whitelist:

```python
oracle = Oracle(
    allowed_commitment_templates=["RECOVERY_N_OF_M", "SLEEP_MIN_HOURS_EVERY_NIGHT", ...]
)
verdict = oracle.settle(..., commitment_template_id="RECOVERY_N_OF_M")
```

Commitments that don't match a whitelist id fail the gate deterministically — this is the primary defense against prompt injection and free-form ambiguity.

## Env requirements

- `ANTHROPIC_API_KEY` for the primary oracle
- `GEMINI_API_KEY` or `GOOGLE_API_KEY` for the confirmation oracle

## Tests

```bash
cd ..  # repo root
python3 -m keep_oracle.test_oracle
```

6 smoke tests, no LLM calls. All pass.

## Integration notes for /Users/p/Code/keep

1. `pip install anthropic>=0.40 google-generativeai>=0.8` (or add to requirements).
2. Copy `keep_oracle/` into the Keep project OR add this repo as a path dependency.
3. Replace the current settlement call with `Oracle().settle(...)`.
4. Wire `pause_for_review` outcomes to your admin queue (or Telegram bot, or email).
5. Define your commitment templates and pass the whitelist to `Oracle(allowed_commitment_templates=...)`.
