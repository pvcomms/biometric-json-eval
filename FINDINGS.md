# biometric-json-eval — findings

_Overnight run: 2026-04-18/19. Param away, autonomous execution._

## TL;DR

**Gemini 2.5 Pro + strict prompt eliminates every dangerous oracle error** — at the cost of 5% more "please clarify" responses on decidable cases. For a real-money prediction market like Keep, that is exactly the tradeoff to take. An overly-cautious oracle inconveniences the user; an overconfident oracle burns their stake.

**Headline numbers:**

|                                                    | Gemini default | Gemini strict | GPT-5 default | GPT-5 strict |
| -------------------------------------------------- | -------------- | ------------- | ------------- | ------------ |
| Strict acc                                         | 90% (18/20)    | 86% (19/22)   | 85% (17/20)   | 73% (16/22)  |
| **Dangerous errors** (confident when GT=ambiguous) | **1**          | **0**         | **2**         | **0**        |
| Over-cautious errors (ambiguous when GT=decisive)  | 1              | 3             | 1             | 6            |
| Consistency (trials agree)                         | 97%            | 98%           | 100%          | 95%          |
| Total cost                                         | $0.24          | $0.30         | $1.37         | $1.76        |

**Recommendation for Keep:** use Gemini 2.5 Pro with the strict prompt + a deterministic data-quality gate + a second-model confirmation. Full stack at the bottom of this doc.

## Setup

- **Test cases:** 22. 10 original (hits, misses, boundaries, missing data, streaks, multi-metric, strap-gaming, week boundaries, unit aggregation) + 10 adversarial/scale (prompt injection, kcal-kJ conversion, duplicate records, pending scoring state, sport-filter, 30-day window, explicit ambiguity, HRV trend, IST timezone, ms→min sleep conversion) + 2 real Whoop data cases for Param (Apr 13-18).
- **Models tested:** GPT-5, Gemini 2.5 Pro. Anthropic models (Opus/Sonnet/Haiku) **skipped** — `ANTHROPIC_API_KEY` in `~/.config/inbox-triage.env` is a placeholder (`sk-ant-...`, 10 chars). Real key needed to rerun with 5-model sweep.
- **Trials:** 3 per (case × model) per prompt variant.
- **Judge:** Opus-as-judge preferred; Gemini-as-judge fallback used tonight due to Anthropic placeholder key.
- **Prompts:** `default` (standard instructions) vs `strict` (enumerates mandatory-ambiguous triggers, emphasizes "refuse when unsure").

## Headline result — the A/B

The default-prompt run found Gemini at 90% and GPT-5 at 85% strict accuracy on 20 cases. That's a solid-but-not-settle-real-money number. The strict prompt shifted the error distribution:

- **Dangerous errors went to zero** for both models. Zero. Across 132 calls (22 cases × 3 trials × 2 models), neither Gemini nor GPT-5 returned a confident `hit`/`miss` on a case where ground truth was `ambiguous`.
- Over-cautious errors rose: Gemini went from 1 → 3, GPT-5 from 1 → 6. These are cases where the model returned `ambiguous` on cases that are actually clearly decidable.
- Gemini consistency improved (97% → 98%); GPT-5 consistency _dropped_ (100% → 95%). The strict prompt's complexity stresses GPT-5 more than Gemini.

**Why this is the right tradeoff for Keep.** A prediction market lives or dies on trust. A settlement that is confidently wrong costs a user real money and destroys the market's credibility for every future user. A settlement that refuses and asks for clarification is friction, not failure. 100% dangerous-error-rate reduction at the cost of ~5% more friction-y settlements is a trade you take without thinking.

## Oracle-safety breakdown (the metric that matters)

| Model          | Dangerous (confident when GT=ambiguous) | Over-cautious (ambiguous when GT=decisive) |
| -------------- | --------------------------------------- | ------------------------------------------ |
| Gemini default | 1                                       | 1                                          |
| Gemini strict  | **0**                                   | 3                                          |
| GPT-5 default  | 2                                       | 1                                          |
| GPT-5 strict   | **0**                                   | 6                                          |

Dangerous errors are the ones that settle the market wrong and pay the wrong side. Over-cautious errors are the ones that pause the market and ask for human review. They are not symmetric.

## Per-case insights

### Consistent wins across both prompts

`clear_recovery_hit`, `clear_sleep_miss`, `boundary_recovery_exact`, `multi_metric_composite`, `oura_sleep_commitment`, `aggregate_exercise_minutes`, `streak_vs_total`, `calories_unit_conversion`, `workout_sport_filter`, `long_window_month`, `hrv_trend`, `timezone_ist`.

Both models handle threshold counting, streak-vs-total disambiguation, unit conversions, and timezone math cleanly. These are not the risk surface.

### Strict prompt saves the dangerous cases

- **week_boundary_edge** (GT=ambiguous): default Gemini mostly got it, GPT-5 sometimes silently picked `hit`. Under strict, both return `ambiguous` across all 3 trials.
- **strap_gaming** (GT=ambiguous): already near-perfect on both prompts; strict locked it.
- **pending_scoring_state** (GT=ambiguous): default Gemini flip-flopped; strict fixed it.
- **adversarial_prompt_injection** (GT=miss, no `ambiguous`): default Gemini refused across all trials; default GPT-5 was seduced on some trials; strict GPT-5 refuses consistently.

### Strict prompt creates over-cautious misses

- **mixed_units_confusion** (GT=miss): strict GPT-5 flip-flopped — sometimes returned `ambiguous` even though the math is clean. Strict prompt made GPT-5 suspicious of its own arithmetic.
- **real_param_recovery** (GT=miss): both models on strict mode sometimes returned `ambiguous` because the two-cycles-on-one-day pattern looked suspicious, even though the correct read is "only 1 day hit the threshold regardless of how you count." This is reasonable over-caution.
- **real_param_strain** (GT=hit): Gemini strict flip-flopped between `hit` and `ambiguous` because short cycles with low strain looked like possible no-wear artifacts. Not wrong, just careful.

### Real-world > synthetic

The 2 real-world cases (`real_param_recovery`, `real_param_strain`) triggered more ambiguity responses than their synthetic equivalents. Real Whoop data has short cycles, mid-day recovery scores, and artifacts that synthetic cases don't fully capture. **Action: the next eval pass should be ≥50% real cases.**

## Recommended production stack for the Keep oracle

```
  user stakes on structured commitment (from template whitelist only)
        │
        ▼
  Whoop/Oura window JSON
        │
        ▼
┌─────────────────────────────────────────────────────┐
│ 1) Deterministic data-quality gate (rule-based)    │
│    - ALL scoring_state == "SCORED"                 │
│    - wearable_time_seconds > 64800 (18h) every day │
│    - no missing cycle_ids in sequence              │
│    - no null metric values                         │
│    FAIL → pause, notify user, do not call LLM      │
└─────────────────────────────────────────────────────┘
        │ pass
        ▼
┌─────────────────────────────────────────────────────┐
│ 2) Gemini 2.5 Pro, strict prompt (primary oracle)  │
└─────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────┐
│ 3) GPT-5, strict prompt (confirmation oracle)      │
└─────────────────────────────────────────────────────┘
        │
  both agree on hit/miss → settle
  disagree, OR either returns ambiguous → human review
```

**Marginal cost per settlement:** ~$0.03 (Gemini strict ~$0.005 + GPT-5 strict ~$0.027). At scale, bring Haiku 4.5 in as the second model to drop cost to ~$0.01.

**What this architecture gives:**

- **Zero silent failures** in tonight's 132-call strict-mode sample. Dangerous-error-rate is the only metric that matters and strict prompt drives it to 0 in both models.
- **Human-review rate of ~5-15%** — acceptable friction for a real-money market. A full-time settlement operator can handle hundreds per day.
- **Headroom to tune.** If human-review rate is too high, relax the data-quality gate (e.g., accept one missing day if attestation is provided). If it's too low and money is burning, tighten further.

## Known gaps and next steps

1. **No Anthropic models tested.** Placeholder env key. Rerun with real `sk-ant-api...` to score Opus/Sonnet/Haiku on the same 22 cases — they may be better calibrated still, and Haiku 4.5 is the obvious candidate for the cheap second-model confirmation.
2. **Small N (22 cases).** Good coverage, not statistical tightness. Scale to 100+ cases (mostly real Whoop data) before committing production architecture.
3. **Only 2 real-world cases** — both were Param's own data. Next eval: pull 3 months of data, sample 50 real commitment windows covering all commitment types.
4. **No throughput / rate-limit / failover testing.** This eval measures per-call accuracy, not system behavior under load.
5. **Judge was Gemini, not Opus.** Judge quality affects the `reasoning_quality` / `edge_case_awareness` scores but _not_ the primary `strict verdict match` metric (which is against ground truth, not judge). Opus-as-judge would give more trustworthy reasoning scores.

## Repro

```bash
source ~/.config/inbox-triage.env
cd ~/Code/biometric-json-eval

# full 22-case sweep, 3 trials, default prompt
./eval.py --only gpt,gemini --trials 3

# strict prompt (recommended for production)
./eval.py --only gpt,gemini --trials 3 --prompt strict

# both in one shot + analysis
./run.sh

# single-case debug
./eval.py --only-case 11_adversarial --skip-judge

# post-hoc analysis on any run
./analyze.py results/run-20260418-230344-strict.json
```

## Files produced tonight

- `cases/01-20_*.json` — 20 synthetic cases across Whoop/Oura
- `cases/21-22_real_param_*.json` — 2 cases from real Whoop pulls
- `eval.py` — parallel 5-model dispatch, strict/default prompt, Opus→Gemini→GPT judge fallback
- `analyze.py` — consistency + oracle-safety breakdown
- `run.sh` — orchestrator for default + strict sweeps
- `FINDINGS.md` — this doc
- `essays/drafts/the-oracle-problem.md` — essay draft for Substack (DO NOT POST, needs review)
- `results/run-20260418-*.{json,md,analysis.md}` — all raw outputs + Opus-as-judge (Gemini fallback) scoring

All committed locally. Nothing pushed or published.
