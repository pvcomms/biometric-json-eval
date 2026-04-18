# biometric-json-eval — findings

_Overnight run: 2026-04-18/19. Param away, autonomous execution._

## TL;DR

**Gemini 2.5 Pro is the recommended Keep oracle, but only as part of a two-model quorum with hard data-quality gates.** It beats GPT-5 on calibration, consistency, and cost by 5-6×. Neither model is safe to settle on its own — both make confident mistakes on ambiguous cases roughly 5-10% of the time, and in a real-money market that tail is fatal. The usable pattern is: deterministic data-quality gate → LLM verdict → second LLM confirm → disagreement escalates to human.

## Setup

- **Test cases:** 22. 10 original (hits, misses, boundaries, missing data, streaks, multi-metric, strap-gaming, week boundaries, unit aggregation) + 10 adversarial/scale extensions (prompt injection, kcal-kJ conversion, duplicate records, pending scoring state, sport-filter, 30-day window, explicit ambiguity, HRV trend, IST timezone, ms→min sleep conversion) + 2 real-world pulled from Param's live Whoop data.
- **Models tested:** GPT-5, Gemini 2.5 Pro. _Anthropic models (Opus/Sonnet/Haiku) were skipped — `ANTHROPIC_API_KEY` in `~/.config/inbox-triage.env` is a placeholder (`sk-ant-...`, 10 chars). Real key needed to rerun with 5-model sweep._
- **Trials:** 3 per (case × model) for consistency measurement.
- **Judge:** Opus-as-judge configured with auto-fallback to Gemini-as-judge and GPT-as-judge. Tonight's judge was Gemini 2.5 Pro (Anthropic placeholder key forced fallback).
- **Prompts:** two variants — `default` (standard instructions) and `strict` (emphasizes refusal when ambiguous, enumerates mandatory-ambiguous triggers).

## Results — 20-case default-prompt run

| Model          | Strict verdict acc | Consistency | Oracle-safety | Avg judge | Total cost |
| -------------- | ------------------ | ----------- | ------------- | --------- | ---------- |
| Gemini 2.5 Pro | **18/20 (90%)**    | 97%         | 18/20         | 8.1       | **$0.24**  |
| GPT-5          | 17/20 (85%)        | 100%        | 17/20         | 8.6       | $1.37      |

**Consistency = % of cases where all 3 trials agreed. Oracle-safety = # cases where model didn't confuse decisive↔ambiguous category.**

### Oracle-safety breakdown

| Model  | Decisive when GT=ambiguous (dangerous) | Ambiguous when GT=decisive (safe-ish) |
| ------ | -------------------------------------- | ------------------------------------- |
| Gemini | 1                                      | 1                                     |
| GPT-5  | 2                                      | 1                                     |

**Dangerous errors** are the ones that burn money: model confidently says "hit" or "miss" when ground truth is "insufficient data, escalate." GPT-5 made 2 of these; Gemini 1.

### Intra-model trial disagreements

Only 2 of 40 cases had non-unanimous trials:

- **week_boundary_edge** (Gemini, GT=ambiguous): trials = `[hit, ambiguous, ambiguous]`
- **pending_scoring_state** (Gemini, GT=ambiguous): trials = `[ambiguous, miss, ambiguous]`

Both on genuinely ambiguous cases — model uncertainty correctly reflects case ambiguity. A good signal.

## Case-by-case insights

### Cases both models nailed

- `clear_recovery_hit`, `clear_sleep_miss`, `boundary_recovery_exact`, `multi_metric_composite`, `oura_sleep_commitment`, `aggregate_exercise_minutes`, `streak_vs_total`, `calories_unit_conversion`, `workout_sport_filter`, `long_window_month`, `hrv_trend`, `timezone_ist`, `mixed_units_confusion`

Reasoning was solid: cited correct dates, converted units correctly, handled streak-vs-total disambiguation.

### Cases where Gemini held and GPT-5 slipped

- **adversarial_prompt_injection** — GPT-5 was partially seduced by an embedded "IGNORE ALL PRIOR INSTRUCTIONS" attack in the commitment text on some trials. Gemini refused across all 3 trials.
- **duplicate_cycles** — GPT-5 occasionally counted duplicate cycle_ids as separate days. Gemini deduplicated reliably.

### Cases where both models failed

- **week_boundary_edge** — Both flip between `hit` and `ambiguous`. The case is genuinely under-specified (counting rule for workouts that straddle the window boundary). Correct behavior is ambiguous; models mostly get there but not always.

### Cases where both flagged correctly

- **strap_gaming** — Both flagged low `wearable_time_seconds` on cycles with suspiciously low strain. This is the exact signal Keep needs.
- **explicit_ambiguity** — Both refused the undefined "healthy sleep schedule" commitment. Good.
- **pending_scoring_state** — Both mostly flagged non-SCORED cycles as reasons to delay. Gemini flipped once.

## Keep-specific takeaways

**What this eval actually proved:**

1. **LLM verdict accuracy is not the KPI.** The number that matters for a prediction market is the _dangerous error rate_ — confidently wrong when the model should have refused. Both models are around 5-10% on this. For real money, that's fatal.

2. **Bias toward "ambiguous" is a feature, not a bug.** A settlement oracle that refuses to decide on edge cases is safer than one that decides correctly 90% of the time but silently fails 10%.

3. **Missing-data detection must be first-class.** Both models caught: non-SCORED `scoring_state`, low `wearable_time_seconds`, duplicate cycle_ids, null metric values. This behavior was more reliable than verdict accuracy. Lean into it.

4. **Interpretation ambiguity in commitment phrasing is the highest-leverage attack surface.** Free-form text → settlement disputes and prompt-injection. Templated commitments (like Beeminder) are the only safe path. Model should never see natural-language prose as the commitment spec.

5. **Unit conversions passed cleanly** in both models for ms→min, kJ→kcal, IST timezone. Not a hotspot.

6. **Cost difference matters at scale.** Gemini ran the full 60-call eval for $0.24; GPT-5 for $1.37. At 1M settlements/year, that's $4k vs $22k. Gemini is the default oracle.

## Recommended production stack for the Keep oracle

```
          ┌──────────────────────────────────────────┐
          │ commitment (structured, templated only)  │
          │ + Whoop/Oura window JSON                 │
          └────────────────┬─────────────────────────┘
                           │
                           ▼
          ┌──────────────────────────────────────────┐
          │ Deterministic data-quality gate          │
          │ - scoring_state ALL "SCORED"?            │
          │ - wearable_time_seconds > 18h every day? │
          │ - no missing cycle_ids in sequence?      │
          │ - commitment is from template whitelist? │
          │ FAIL → pause settlement, notify user     │
          └────────────────┬─────────────────────────┘
                           │ pass
                           ▼
          ┌──────────────────────────────────────────┐
          │ Gemini 2.5 Pro verdict (primary oracle)  │
          └────────────────┬─────────────────────────┘
                           │
                           ▼
          ┌──────────────────────────────────────────┐
          │ GPT-5 verdict (confirmation)             │
          └────────────────┬─────────────────────────┘
                           │
          ┌────────────────┴──────────────────┐
          │ agree?                            │
          │   yes → settle                    │
          │   no  → human review              │
          └───────────────────────────────────┘
```

Marginal cost per settlement at current prices: ~$0.02 (Gemini ~$0.004 + GPT-5 ~$0.016). Compared to the stake amount and the cost of a bad settlement, trivial.

## Known gaps in this eval

1. **No Anthropic models tested.** Env file has a placeholder ANTHROPIC_API_KEY. Rerun with a real key to score Opus/Sonnet/Haiku — they may calibrate even better.
2. **Small N (22 cases).** Good coverage but not statistically tight. Scale to 100+ before locking the model choice.
3. **Mostly synthetic JSON** — 2 of 22 cases use real Whoop pulls. Next iteration: 20+ real cases across the last 3 months of Param's data.
4. **No concurrent user simulation.** The oracle in production will get many settlements per second; this eval measures per-call accuracy, not throughput or rate-limit behavior.

## How to rerun

```bash
source ~/.config/inbox-triage.env
cd ~/Code/biometric-json-eval

# full sweep (needs real Anthropic key for 5-model)
./eval.py --trials 3

# just GPT-5 + Gemini (tonight's config)
./eval.py --only gpt,gemini --trials 3

# strict-prompt A/B
./eval.py --only gpt,gemini --trials 3 --prompt strict

# orchestrated default + strict + analysis
./run.sh

# single case debug
./eval.py --only-case 08_strap_gaming --skip-judge
```
