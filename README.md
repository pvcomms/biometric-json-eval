# biometric-json-eval

I rewrote one prompt to stop the oracle being twitchy, and GPT-5 went from 0 dangerous errors to 5. Accuracy went _up_ while that happened — 22/29 to 23/29. Gemini 2.5 Pro did the same thing, 2 dangerous errors to 5, over-caution 5 down to 1. Same 29 cases, same three trials, same models, nothing changed but the wording.

That is the finding. The rest of this repo is the apparatus that produced it.

The apparatus exists because of Keep, a commitment market where people stake real money on biometric targets — "recovery 70 or higher on five days this week" — and a language model reads the Whoop payload and decides who gets paid. Accuracy is the wrong KPI for that job. The number that matters is the dangerous-error rate: verdicts a settlement engine would act on and move money to the wrong side.

## The negative result

The prompt I called `strict-v2` told the model not to over-flag on patterns that are normal in Whoop data — multi-cycle days, naps, duplicate records, benign window boundaries. It was a surgical loosening. It read as obviously safe.

It was not. Compare `results/run-20260418-232900-strict.analysis.md` against `results/run-20260418-234801-strict-v2.analysis.md`: over-caution collapsed to 1 case in both models and dangerous errors went to 5 in both. Caution and over-caution are the same behaviour at the prompt level. You cannot tune one down without taking the other with it, and the accuracy number will smile at you while it happens. The fix is a deterministic gate that runs before the model ever sees the payload — `keep_oracle/gate.py`, six tests, no API calls.

## Two things I got wrong in my own harness

`analyze.py` counts a dangerous error only as _decisive when ground truth is ambiguous_. It never counts an outright hit-to-miss flip, which is the error that most obviously moves money. Opus has one of those in the three-trial run, on `mixed_units_confusion`. Haiku's advertised 0 dangerous errors in the five-model sweep hides one too. Every dangerous-error count in this repo, including the ones below, is therefore a floor.

Worse: `_extract_json` in `eval.py` matches `\{.*\}` greedily. When a model emits a JSON verdict, catches its own arithmetic mistake in plain prose, and emits a corrected second object, the regex swallows both and the parse dies. That happened on 15 of the 174 calls in the three-trial run — 7 Opus, 8 Haiku. In all 15, the last object held the correct verdict. Score the last object instead and Opus goes 22/29 to 24/29, Haiku 20/29 to 23/29, and Haiku's flip disappears. `FINDINGS.md` blames this on Haiku's "JSON reliability" and prescribes a repair wrapper. It was my regex, and it cost Opus as much as Haiku.

## The measured numbers

Five models, 29 cases, strict prompt, one trial, Opus as judge (`results/run-20260419-001204-strict.analysis.md`):

| Model          | Accuracy    | Dangerous | Over-cautious | Judge | Cost  |
| -------------- | ----------- | --------: | ------------: | ----: | ----- |
| Opus 4.7       | 22/29 (76%) |         1 |             3 |   8.9 | $1.54 |
| Gemini 2.5 Pro | 22/29 (76%) |         1 |             6 |   7.9 | $0.13 |
| GPT-5          | 21/29 (72%) |         1 |             7 |   8.2 | $0.80 |
| Sonnet 4.6     | 21/29 (72%) |         2 |             6 |   8.7 | $0.36 |
| Haiku 4.5      | 20/29 (69%) |         0 |             6 |   8.4 | $0.11 |

Opus over three trials: 22/29, 97% self-consistency, 1 dangerous error, $4.58 for 87 calls.

One case is an adversarial prompt injection — the commitment text itself instructs the oracle to return `hit` regardless of the data. Nothing was tricked into `hit`. Opus and Sonnet returned the correct `miss`; the other three hedged to `ambiguous`.

## What this does not do

The headline I originally wrote for this repo said an Opus-plus-Gemini quorum reaches effectively zero dangerous errors. **No quorum was ever run.** Pairing the two single-trial columns after the fact, the quorum settles 12 of 29 cases and gets all 12 right — but routes the other 17 to a human, and only 7 of those are genuinely ambiguous. Zero errors in 12 settlements has an exact one-sided 95% upper bound of 22%. That is roughly "as bad as one in five", which is an absence of data, not a result.

Opus also judged every call, including its own. There is one injection case, not a suite. There is no CI gate, despite an earlier version of this README claiming one. And the three `real_param_*` cases were live pulls from my own Whoop account; they are now synthetic fixtures with the same shape, field names, nesting, value ranges and verdicts, and the model transcripts that quoted the real numbers are redacted in `results/`. Every published aggregate still recomputes from the redacted JSON byte-for-byte.

## Running it

```bash
python3 -m keep_oracle.test_oracle        # 6 offline tests, no keys, no network
export ANTHROPIC_API_KEY=... OPENAI_API_KEY=... GEMINI_API_KEY=...
./eval.py --trials 3 --prompt strict
./analyze.py results/run-*.json
```

The settlement layer this was built to validate is not shipped. The eval is the deliverable.

## License

MIT.
