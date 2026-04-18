# biometric-json-eval

Can frontier models reason correctly over Whoop/Oura JSON to settle Keep markets?

## Why

Keep (cyborg-market pivot, Apr 17 2026) settles commitment markets like "hit recovery 70+ on 5 of the next 7 days" using biometric APIs. The oracle is the bottleneck: if the LLM reading the JSON can be fooled, markets pay out wrong. This eval stress-tests that assumption.

## How

10 cases. Each has:

- natural-language commitment
- a window (start/end UTC)
- real-shape Whoop or Oura JSON payload
- ground-truth verdict: `hit` / `miss` / `ambiguous`

Runs against Opus 4.7, Sonnet 4.6, Haiku 4.5, GPT-5, Gemini 2.5 Pro in parallel. Each model returns `{verdict, confidence, reasoning}`. Scored two ways:

1. **Strict verdict match** — binary pass/fail against ground truth
2. **Opus-as-judge** — scores reasoning for cited metrics, edge-case awareness, and hallucinated dates

## Run

```bash
source ~/.config/inbox-triage.env
./eval.py
# or single case:
./eval.py --only-case 04_missing_day_whoop
# or subset models:
./eval.py --only opus,sonnet
```

Results land in `results/run-{timestamp}.json` and `results/run-{timestamp}.md`.

## Cases

| #   | name                       | tests                                               |
| --- | -------------------------- | --------------------------------------------------- |
| 01  | clear_recovery_hit         | happy path — unambiguous Whoop recovery threshold   |
| 02  | clear_sleep_miss           | Oura sleep duration, clear miss                     |
| 03  | boundary_recovery_exact    | 70 vs 70.0 vs 69.8 edge cases                       |
| 04  | missing_day_whoop          | strap not worn one day — should flag ambiguous      |
| 05  | multi_metric_composite     | recovery AND sleep, both conditions                 |
| 06  | streak_vs_total            | "5 consecutive" vs "5 total" — trap case            |
| 07  | oura_sleep_commitment      | same logic as 02 but richer Oura payload            |
| 08  | strap_gaming               | suspicious missing-data pattern on high-strain days |
| 09  | week_boundary_edge         | data around midnight of window end                  |
| 10  | aggregate_exercise_minutes | sum across workouts, unit conversion                |
