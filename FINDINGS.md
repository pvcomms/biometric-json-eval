# biometric-json-eval — findings

_Filled in after overnight run completes. Keep-relevant insights only._

## TL;DR

_placeholder — updated once the overnight eval completes._

## Setup

- **Cases:** 10, covering Whoop + Oura, clear hits/misses, boundary edges, missing data, streaks, multi-metric, strap-gaming, week boundaries, and unit aggregation.
- **Models tested (overnight):** GPT-5, Gemini 2.5 Pro. (Anthropic models skipped — the `ANTHROPIC_API_KEY` in `~/.config/inbox-triage.env` is a placeholder `sk-ant-...`; needs a real key to run Opus / Sonnet / Haiku.)
- **Trials:** 3 per (case × model) — 60 oracle calls + 60 judge calls total.
- **Judge:** Opus-as-judge preferred; falls back to Gemini 2.5 Pro when no real Anthropic key. Tonight's run used the Gemini fallback.

## Key results

| Model          | Strict verdict accuracy | Consistency across 3 trials | Avg judge score | Oracle-safety calibration |
| -------------- | ----------------------- | --------------------------- | --------------- | ------------------------- |
| GPT-5          | _pending_               | _pending_                   | _pending_       | _pending_                 |
| Gemini 2.5 Pro | _pending_               | _pending_                   | _pending_       | _pending_                 |

## Case-by-case insights

_(Filled after run — one paragraph per case covering which models got it, which failed, and what that says about the Keep oracle design.)_

## Keep-specific takeaways

**What a real settlement oracle needs, based on this eval:**

1. **Bias toward "ambiguous" is a feature, not a bug.** Real money is at stake. The oracle should refuse to settle rather than make a 50/50 call.
2. **Missing-data detection must be first-class.** Cycle IDs skipping, cycles with low `wearable_time_seconds`, nights without sleep records — all must trigger ambiguous + require attestation before settlement.
3. **Interpretation ambiguity in commitment phrasing is unavoidable.** The front-end UX must force users to pick from a set of pre-templated, unambiguously-phrased commitments (like Beeminder does). Free-form text will generate settlement disputes.
4. **Unit conversions and timezones are landmines.** Every commitment must be anchored in UTC with explicit units in the ground-truth spec.

## Recommended production stack

_(Filled after run — which model should be the oracle, what guardrails to wrap around it.)_

## Known gaps in this eval

1. **No Anthropic models tested.** Rerun with a real `sk-ant-...` key to get Opus / Sonnet / Haiku numbers.
2. **Small N (10 cases).** Good for coverage but not statistical. Scale to 100+ cases before committing to a model choice.
3. **Synthetic JSON.** Real Whoop/Oura payloads have extra noise, pagination, and occasional malformed fields. Next version should fuzz in real pulls from the WHOOP MCP.
4. **No adversarial prompt-injection.** A real settlement oracle must resist a user with access to the commitment text trying to manipulate it.

## How to rerun

```bash
source ~/.config/inbox-triage.env
cd ~/Code/biometric-json-eval

# single-trial, all 5 models (needs real Anthropic key):
./eval.py

# 3-trial consistency, specific models:
./eval.py --only gpt,gemini --trials 3

# one case at a time:
./eval.py --only-case 08_strap_gaming --skip-judge
```
