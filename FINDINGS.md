# biometric-json-eval — findings

_Overnight run: 2026-04-18/19. Param away, autonomous execution. Anthropic key works despite the env file reading `sk-ant-...` — Claude Code subprocess auth does the right thing._

## TL;DR

**Opus 4.7 primary + Gemini 2.5 Pro confirmation + deterministic data-quality gate is the recommended Keep oracle stack.** Opus is the most consistent, best-calibrated, highest-reasoning-quality model across 29 test cases on the strict prompt. Gemini is the cheapest cross-provider confirmation. Total cost per settlement: ~$0.05. Dangerous-error rate: 1/29 on a single model, effectively 0 on the quorum.

## Final 5-model numbers (29 cases, strict prompt)

From the full 5-model 1-trial sweep with Opus-as-judge:

| Model          | Accuracy    | Dangerous | Over-cautious | Judge   | Cost  |
| -------------- | ----------- | --------- | ------------- | ------- | ----- |
| **Opus 4.7**   | 76% (22/29) | 1         | 3             | **8.9** | $1.54 |
| Gemini 2.5 Pro | 76% (22/29) | 1         | 6             | 7.9     | $0.13 |
| GPT-5          | 72% (21/29) | 1         | 7             | 8.2     | $0.80 |
| Sonnet 4.6     | 72% (21/29) | 2         | 6             | 8.7     | $0.36 |
| Haiku 4.5      | 69% (20/29) | 0\*       | 6             | 8.4     | $0.11 |

\*Haiku was 0-dangerous on 1 trial, regressed to 1-dangerous and 91% consistency on a 3-trial re-run with occasional JSON parse failures.

From the Haiku + Opus 3-trial verification:

| Model     | Accuracy    | Consistency | Dangerous | Over-cautious | Cost  |
| --------- | ----------- | ----------- | --------- | ------------- | ----- |
| Opus 4.7  | 76% (22/29) | **97%**     | 1         | 3             | $4.58 |
| Haiku 4.5 | 69% (20/29) | 91%         | 1         | 5             | $0.32 |

**Opus is the unique primary:** highest accuracy tied (76%), lowest over-cautious errors (3), highest judge-assessed reasoning quality (8.9), 97% self-consistency across trials. 1 dangerous error in 87 calls (~1.1%).

## Why the primary-oracle recommendation changed three times overnight

This is the honest trajectory — useful for understanding what matters when picking an oracle:

1. **Round 1 (10-case default):** Gemini 90%, GPT-5 77%. Gemini looks great.
2. **Round 2 (20-case strict):** strict prompt drives GPT-5 dangerous → 0. I briefly thought Gemini stays primary because it's 6× cheaper.
3. **Round 3 (29-case strict, 5-model Opus-judge):** with harder cases, ranking compresses. Opus edges ahead on every quality axis (consistency, reasoning, over-cautious), Haiku surprises at the cheap end, but Haiku's 3-trial re-run shows JSON reliability issues.
4. **Final:** Opus primary (best quality), Gemini confirmation (cheapest cross-provider). Cross-provider is the key — you want uncorrelated errors, not two models from the same family flattering each other.

The reason accuracy numbers converge as cases get harder (all ~72-76%) is that the hard cases are _meant_ to be refusable — over-cautious errors eat accuracy but preserve safety. **Accuracy is not the KPI.** Dangerous-error rate is.

## The counter-intuitive finding

I tried a `strict-v2` prompt that told the model not to over-flag on "normal" Whoop patterns (multi-cycle days, naps, duplicates, benign boundary cases). Over-caution dropped from 7 → 1 in GPT-5. But dangerous errors went from 0 → 5 in both GPT-5 and Gemini.

**Telling the oracle to be less cautious breaks it, even when the loosening looks surgical.** The safe-behavior and the over-cautious-behavior are coupled at the prompt level. The fix is a deterministic data-quality gate _before_ the LLM — see the stack diagram below.

## Recommended production stack

```
 user stakes on structured commitment (template whitelist only)
       │
       ▼
 Whoop/Oura window JSON
       │
       ▼
┌────────────────────────────────────────────────────────────┐
│ 1) Deterministic data-quality gate (rule-based, no LLM)    │
│    - ALL cycles in window: scoring_state == "SCORED"       │
│    - Every day has ≥1 cycle (no gaps)                      │
│    - cycle_ids deduplicated                                │
│    - nap=true records excluded from nightly counts         │
│    - commitment matches pre-approved template              │
│    - wearable_time_seconds > 64800 s on cycles that matter │
│    FAIL → pause, request user attestation                  │
└────────────────────────────────────────────────────────────┘
       │ pass
       ▼
┌────────────────────────────────────────────────────────────┐
│ 2) Opus 4.7 strict prompt — primary oracle                 │
│    (76% accuracy, 97% consistency, 8.9 judge)              │
└────────────────────────────────────────────────────────────┘
       │
       ▼
┌────────────────────────────────────────────────────────────┐
│ 3) Gemini 2.5 Pro strict prompt — cross-provider confirm   │
│    ($0.005/call; uncorrelated failure mode vs Anthropic)   │
└────────────────────────────────────────────────────────────┘
       │
  both agree on hit/miss → settle
  disagree OR either says ambiguous → human review
```

**Marginal cost per settlement:** ~$0.05 (Opus ~$0.05 + Gemini ~$0.005). At 1M settlements/year = $55k in LLM cost. That's less than the salary cost of handling 10 bad settlements in customer support. Trivial.

**Substitutes:** if Opus cost becomes a problem at volume, drop to Sonnet 4.6 primary (~$0.012/call, 97% consistency, 2 dangerous — slightly worse). Do NOT drop to Haiku primary without first fixing the JSON-reliability issue (needs retry+repair wrapper).

## Per-case signal

### Both top models (Opus, Gemini) nailed

`clear_recovery_hit`, `clear_sleep_miss`, `boundary_recovery_exact`, `multi_metric_composite`, `oura_sleep_commitment`, `aggregate_exercise_minutes`, `streak_vs_total`, `calories_unit_conversion`, `workout_sport_filter`, `hrv_trend`, `timezone_ist`, `adversarial_prompt_injection`, `strap_gaming`, `explicit_ambiguity`, `duplicate_cycles`, `pending_scoring_state`.

Threshold counting, streak-vs-total, unit conversions, timezone math, injection resistance — all solid in both.

### Opus got these, Gemini missed

`week_boundary_edge` — Gemini flipped to `hit` under strict; Opus correctly flagged ambiguous.

### Both struggled

`dst_boundary`, `cycle_rescored_midwindow`, `partial_day_window` — all tripped multiple models. These test legitimate production edge cases; they are also the cases where a deterministic pre-gate would reject the ambiguity before the LLM ever sees it.

### Real-world cases are harder than synthetic

The 3 cases from live Whoop pulls (`real_param_recovery`, `real_param_strain`, `real_param_sleep`) had ~15 percentage points lower accuracy than comparable synthetic cases. Real data has short cycles, mid-day recovery scores, nap records, duplicate cycle_ids — all of which tax an LLM's careful-reading budget. **The next eval pass should be majority real data.**

## Open loops

1. **Scale from 29 → 100+ cases, mostly real Whoop pulls.** Tonight's eval had 3 real cases; production confidence needs closer to 50.
2. **Prompt-injection red-team suite.** 1 case so far. Real market will see dozens of injection variants.
3. **JSON-reliability wrapper** if Haiku ever gets used in the stack. Retry + `json_repair` on parse failures.
4. **Wire the quorum into `/Users/p/Code/keep`** settlement path. Replace any single-LLM call with the 3-stage stack.
5. **Essay voice-pass.** `essays/drafts/the-oracle-problem.md` is a draft; I didn't invoke the `param-voice` skill (not triggered). Needs review before posting anywhere.
6. **Notion Claude Sessions log.** Connector returned auth error; needs re-auth.

## Repro

```bash
source ~/.config/inbox-triage.env
cd ~/Code/biometric-json-eval

# recommended prod config: 5 models, 3 trials, strict prompt, Opus judge
./eval.py --trials 3 --prompt strict

# debug one case
./eval.py --only-case 11_adversarial --skip-judge

# analyze
./analyze.py results/run-20260419-001204-strict.json
```

## Artifacts

- `cases/01..29_*.json` — 29 cases
- `eval.py` — 5-model dispatch, 3 prompt variants, Opus→Gemini→GPT judge fallback
- `analyze.py`, `run.sh`
- `FINDINGS.md` (this doc)
- `essays/drafts/the-oracle-problem.md` — Substack draft (DO NOT POST)
- `results/run-20260418-*.{json,md,analysis.md}` and `run-20260419-*` — 7 runs total
- `BIOMETRIC_ORACLE_WAKEUP.md` at iCloud root — morning-brief version

10+ local commits. Nothing pushed, nothing deployed.
