# biometric-json-eval

Benchmark: can a frontier model read Whoop/Oura JSON correctly enough to settle a commitment market?

## Headline result

**On 29 hand-adversarialised cases with the strict-schema prompt, Opus 4.7 scores 76% accuracy, 97% self-consistency across trials, and 1 dangerous error in 87 calls (~1.1%). A cross-provider quorum (Opus primary + Gemini 2.5 Pro confirmation) drops the dangerous-error rate to effectively zero at a marginal cost of ~$0.05 per settlement.** Telling the oracle to be "less cautious" breaks it: a surgical-looking `strict-v2` prompt lifted over-caution from 7 → 1 but pushed dangerous errors from 0 → 5 on both GPT-5 and Gemini. Safe behaviour and over-cautious behaviour are coupled at the prompt level.

## How to run

```bash
source ~/.config/inbox-triage.env   # ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY
./eval.py --trials 3 --prompt strict          # recommended prod config: 5 models, 3 trials, Opus judge
./eval.py --only-case 11_adversarial --skip-judge   # debug a single case
./analyze.py results/run-<timestamp>-strict.json
```

## Method

- 29 JSON cases built from Whoop/Oura payload shapes plus 3 real Param pulls. Each case has a natural-language commitment, a UTC window, and a ground-truth verdict (`hit` / `miss` / `ambiguous`).
- Models return `{verdict, confidence, reasoning}`. Scored on (a) strict verdict match against ground truth and (b) Opus-4.7-as-judge on cited metrics, edge-case awareness, hallucinated dates.
- Separately tracks **dangerous errors** (would move money wrong) vs **over-cautious errors** (refuses a clear verdict). Dangerous-error rate is the KPI, not accuracy.
- Runs 5 models in parallel: Opus 4.7, Sonnet 4.6, Haiku 4.5, GPT-5, Gemini 2.5 Pro.
- Multi-trial mode (`--trials 3`) to measure self-consistency on the same prompt.

## Results

Final 5-model sweep, 29 cases, strict prompt, Opus judge:

| Model          | Accuracy    | Dangerous | Over-cautious | Judge | Cost  |
| -------------- | ----------- | --------: | ------------: | ----: | ----- |
| **Opus 4.7**   | 76% (22/29) |         1 |             3 |   8.9 | $1.54 |
| Gemini 2.5 Pro | 76% (22/29) |         1 |             6 |   7.9 | $0.13 |
| GPT-5          | 72% (21/29) |         1 |             7 |   8.2 | $0.80 |
| Sonnet 4.6     | 72% (21/29) |         2 |             6 |   8.7 | $0.36 |
| Haiku 4.5      | 69% (20/29) |         0 |             6 |   8.4 | $0.11 |

3-trial verification: Opus holds 97% self-consistency, Haiku degrades to 91% with occasional JSON parse failures. Full trajectory, prompt-variant A/B, and the recommended three-stage production stack (deterministic gate → Opus → Gemini) in `FINDINGS.md`.

## Why this exists

Keep (prediction markets settled by biometric APIs) only works if the oracle reading Whoop/Oura JSON is right. "Close enough" isn't close enough when the output writes money. This eval stress-tests the assumption on adversarial cases and recommends a cross-provider quorum where dangerous errors would require correlated failures across Anthropic and Google at once.
