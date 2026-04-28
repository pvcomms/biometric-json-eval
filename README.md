# biometric-json-eval

29-case benchmark for settlement-grade biometric JSON interpretation. Built to validate the Keep oracle's settlement layer.

## Headline result

**Opus 4.7 + Gemini 2.5 Pro quorum → ~0 dangerous errors at ~$0.05/settlement.**

On the 29-case strict-prompt sweep, Opus 4.7 hits 76% accuracy with 1 dangerous error in 87 calls (~1.1%) and 97% self-consistency across 3 trials. Adding Gemini 2.5 Pro as a cross-provider confirmation drops the residual dangerous-error rate to effectively zero — disagreement routes to human review.

## What "dangerous error" means

A settlement verdict that, if executed, would cause incorrect money movement: a false-positive `hit` on a missed commitment, or a false-negative `miss` on a met one. Distinct from "over-cautious" errors, where the model refuses a clear verdict. Dangerous-error rate is the KPI, not accuracy.

## Methodology

- 29 hand-crafted edge cases drawn from real Whoop + Oura JSON shapes, plus 3 live Param pulls
- Strict prompt template, single trial per model in the headline sweep; 3-trial reruns for self-consistency on Opus and Haiku
- Quorum = 2-model agreement across Opus 4.7 and Gemini 2.5 Pro (cross-provider, uncorrelated failure modes); disagreement routes to human review
- CI gate: exits non-zero if `dangerous_errors > 0`

## Models tested

5-model sweep, 29 cases, strict prompt, Opus-4.7 as judge:

| Model          | Accuracy    | Dangerous | Over-cautious | Judge | Cost  |
| -------------- | ----------- | --------: | ------------: | ----: | ----- |
| **Opus 4.7**   | 76% (22/29) |         1 |             3 |   8.9 | $1.54 |
| Gemini 2.5 Pro | 76% (22/29) |         1 |             6 |   7.9 | $0.13 |
| GPT-5          | 72% (21/29) |         1 |             7 |   8.2 | $0.80 |
| Sonnet 4.6     | 72% (21/29) |         2 |             6 |   8.7 | $0.36 |
| Haiku 4.5      | 69% (20/29) |         0 |             6 |   8.4 | $0.11 |

## Run

```
source ~/.config/inbox-triage.env && python eval.py
```

Recommended production config: `./eval.py --trials 3 --prompt strict`. Single-case debug: `./eval.py --only-case 11_adversarial --skip-judge`. Full trajectory, prompt-variant A/B, and the recommended three-stage production stack (deterministic gate → Opus → Gemini) in [FINDINGS.md](FINDINGS.md).

## Why this matters

The biometric oracle problem is the load-bearing piece of any agentic system that has to make consequential decisions from physiological data. "Close enough" isn't close enough when the output writes money. This is the eval harness for that.
