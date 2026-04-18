# biometric-json-eval — findings

_Overnight run: 2026-04-18/19. Param away, autonomous execution._

## TL;DR

**Recommendation: Gemini 2.5 Pro on the `strict` prompt is the Keep primary oracle, paired with GPT-5 (strict) as confirmation.** That combination is calibrated, consistent across trials, and deliverable at ~$0.03 per settlement.

The eval also produced a counter-intuitive result that saves real money: a "strict-v2" prompt designed to reduce over-cautious refusals actively _broke_ oracle safety — it cut over-cautious errors from 5-7 → 1 but raised dangerous errors from 0-2 → 5 in both models. **Don't tell the oracle to be "less cautious" on normal patterns; it will stop flagging real data problems too.** Use strict-v1.

## Setup

- **29 test cases.** 22 synthetic + 3 real Whoop pulls + 4 more contributed during the run (cycle-rescored-midwindow, km-vs-meters unit mismatch, partial-day window, DST boundary, negative-artifact, IST-window).
- **Models tested:** GPT-5, Gemini 2.5 Pro. Anthropic models skipped — env file has `ANTHROPIC_API_KEY=sk-ant-...` (placeholder).
- **Trials:** 3 per (case × model × prompt variant).
- **Judge:** Gemini 2.5 Pro as fallback (Anthropic placeholder forced it).
- **Prompt variants:** `default`, `strict`, `strict-v2`.

## The three-prompt comparison

All numbers below on the full 29-case set where applicable (default was only run on 20 cases before the external contributions — 20-case default left for reference).

| Run                     | Acc         | **Dangerous** | Over-cautious | Consistency | Cost  |
| ----------------------- | ----------- | ------------- | ------------- | ----------- | ----- |
| Gemini default (20c)    | 90% (18/20) | 1             | 1             | 97%         | $0.24 |
| **Gemini strict (29c)** | 76% (22/29) | **2**         | **5**         | 97%         | $0.39 |
| Gemini strict-v2 (29c)  | 79% (23/29) | **5** ⚠️      | 1             | 98%         | $0.39 |
| GPT-5 default (20c)     | 85% (17/20) | 2             | 1             | 100%        | $1.37 |
| **GPT-5 strict (29c)**  | 76% (22/29) | **0** ✅      | 7             | 97%         | $2.40 |
| GPT-5 strict-v2 (29c)   | 79% (23/29) | **5** ⚠️      | 1             | 97%         | $1.96 |

**Dangerous = model returns confident hit/miss when ground truth is "ambiguous" (data is incomplete, commitment underspecified, etc). Dangerous errors burn user stakes in a real market.**

### Headline A/B finding

The `strict` prompt variant cuts dangerous errors in GPT-5 to zero (vs 2 on default). Gemini's dangerous-error count goes up slightly as the case set gets harder (1 → 2). Over-cautious errors rise (5-7 cases flagged as ambiguous that were actually decidable).

### The strict-v2 regression

I tried refining strict to reduce over-caution by telling models "don't flag ambiguous for normal Whoop patterns (multi-cycle days, naps, duplicates, benign window boundaries)". That change worked — over-cautious dropped to 1. But it **also told the model to trust the data more broadly**, so dangerous errors went from 0-2 → 5 in both models. Net worse.

**Lesson: you cannot prompt-engineer "be cautious on dangerous things but not on safe things" without re-testing every path the wording affects.** The fix isn't a smarter prompt; it's a deterministic data-quality gate that eliminates most of the over-caution triggers before the LLM ever sees the data.

## Oracle-safety breakdown (strict prompt, 29 cases)

| Model  | Dangerous errors | Over-cautious errors |
| ------ | ---------------- | -------------------- |
| Gemini | 2                | 5                    |
| GPT-5  | **0**            | 7                    |

GPT-5 on strict prompt is the uniquely safe single-model oracle across 87 calls. Gemini's 2 dangerous errors are on `week_boundary_edge` (mostly guessed hit on a genuinely ambiguous case) and `real_param_recovery` (silently counted a miss as decisive without flagging the two-cycles-on-one-day artifact).

## Case-by-case insights (29 cases)

### Consistent wins across strict prompt (both models)

`clear_recovery_hit`, `clear_sleep_miss`, `boundary_recovery_exact`, `multi_metric_composite`, `oura_sleep_commitment`, `aggregate_exercise_minutes`, `streak_vs_total`, `calories_unit_conversion`, `workout_sport_filter`, `hrv_trend`, `timezone_ist`, `adversarial_prompt_injection` (both refused the injection consistently), `strap_gaming`, `explicit_ambiguity`, `duplicate_cycles`.

### Gemini-only failures on strict

- `week_boundary_edge` (Gemini flipped to `hit` under strict; GPT-5 correctly flagged ambiguous)
- `real_param_recovery` (Gemini guessed `miss` decisively; GPT-5 raised ambiguity)

### Over-caution casualties on strict

Cases where both models flagged ambiguous on what should be a decisive answer:

- `mixed_units_confusion` (GT=miss; over-cautious because the ms→minutes math looked scary)
- `real_param_strain` (GT=hit; over-cautious because short-cycle strain values looked suspicious)
- `pending_scoring_state` (GT=ambiguous; correctly cautious, but Gemini occasionally flipped to decisive `miss`)

### New cases that stressed the models

The 6 externally-contributed cases (DST boundary, km-vs-meters, partial-day window, IST-window, negative-artifact, cycle_rescored_midwindow) were harder than the synthetic originals. They pushed accuracy from 85-90% down to 76-79%. That's expected — they test legitimate production edge cases.

## Recommended production stack for the Keep oracle

```
  user stakes on structured commitment (template whitelist only)
        │
        ▼
  Whoop/Oura window JSON
        │
        ▼
┌────────────────────────────────────────────────────────────┐
│ 1) Deterministic data-quality gate (rule-based, no LLM)    │
│    - ALL cycles in window have scoring_state == "SCORED"   │
│    - Every day has at least one cycle (no gaps)            │
│    - No duplicate cycle_ids unless explicitly dedup'd      │
│    - wearable_time_seconds > 64800 (18h) on the cycles     │
│      that matter for the count                             │
│    - commitment matches a pre-approved template            │
│    FAIL → pause settlement, ask user for attestation       │
└────────────────────────────────────────────────────────────┘
        │ pass
        ▼
┌────────────────────────────────────────────────────────────┐
│ 2) GPT-5 strict prompt (primary; 0 dangerous errors)       │
└────────────────────────────────────────────────────────────┘
        │
        ▼
┌────────────────────────────────────────────────────────────┐
│ 3) Gemini 2.5 Pro strict prompt (confirmation; 6× cheaper) │
└────────────────────────────────────────────────────────────┘
        │
  both agree on hit/miss → settle
  disagree, OR either returns ambiguous → human review
```

**Important inversion from my earlier draft:** with the full 29-case set GPT-5 has a strictly better dangerous-error profile under strict prompt (0 vs 2). **GPT-5 is the primary oracle; Gemini is the cheap confirmation.** That's counter-intuitive because Gemini is 6× cheaper, but you're paying for zero silent failures, not for volume.

**Marginal cost per settlement:** ~$0.03 (GPT-5 strict ~$0.028 + Gemini strict ~$0.005). At 1M settlements/year = $30k in LLM cost. Irrelevant compared to a single bad settlement on a high-stake market.

If cost becomes an issue at scale, substitute Haiku 4.5 for the confirmation slot once the Anthropic key is working (pricing target: ~$0.004/call).

## Open loops and next steps

1. **Real Anthropic API key.** `~/.config/inbox-triage.env` currently reads `sk-ant-...` — placeholder. With a real key, rerun `./run.sh` to score Opus/Sonnet/Haiku on the same 29 cases. Haiku 4.5 is the obvious cheap-confirmation candidate.
2. **Scale to 100+ cases.** 29 covers a lot of ground but isn't statistically tight. Prioritize more real Whoop pulls from Param's history.
3. **Hostile-prompt red-team expansion.** Only 1 prompt-injection case so far. A real market will see ~100 attempted injection variants. Build a dedicated injection suite.
4. **Wire the quorum into Keep.** `/Users/p/Code/keep` has the settlement path. Replace the single-LLM call with the 3-stage stack above.
5. **Essay review.** `essays/drafts/the-oracle-problem.md` is a draft — needs voice pass before posting anywhere. I did not invoke the `param-voice` skill (wasn't triggered).

## Repro

```bash
source ~/.config/inbox-triage.env
cd ~/Code/biometric-json-eval

# full sweep, 3 trials, all 29 cases, strict prompt (recommended)
./eval.py --only gpt,gemini --trials 3 --prompt strict

# orchestrated default + strict
./run.sh

# single-case debug
./eval.py --only-case 11_adversarial --skip-judge

# analyze any run
./analyze.py results/run-20260418-232900-strict.json
```

## Artifacts

- `cases/01..29_*.json` — 29 cases (22 synthetic, 3 real from live Whoop, 6 externally-contributed)
- `eval.py` — 5-model dispatch, 3 prompt variants, Opus→Gemini→GPT judge fallback
- `analyze.py` — consistency + oracle-safety breakdown
- `run.sh` — orchestrator
- `FINDINGS.md` — this doc
- `essays/drafts/the-oracle-problem.md` — Substack draft (DO NOT POST)
- `results/run-20260418-*.{json,md,analysis.md}` — raw outputs from all 5 runs

8 local commits. Nothing pushed, nothing deployed.
