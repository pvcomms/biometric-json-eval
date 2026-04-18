---
title: "The Oracle Problem"
dek: "Keep settles commitments using Whoop JSON. Here's what happened when I asked five models to be the judge."
status: DRAFT — do not publish without review
source: biometric-json-eval run-20260418
author: Param
---

Real money is riding on whether a language model can read a Whoop payload correctly.

That sentence should scare you.

Keep — the prediction market I'm building — lets users stake money on biometric commitments. "I'll hit recovery 70+ on five days this week. If I don't, three hundred rupees go to the opposition party's campaign." Whoop's API returns a JSON blob. An LLM reads the blob. The LLM settles the market.

The entire thing rises or falls on the oracle.

So this weekend I built [biometric-json-eval](https://github.com/param/biometric-json-eval): twenty test cases covering clear hits, clear misses, boundary days, missing cycles, strap-gaming patterns, unit conversions from kilojoules, and — my favorite — a case where the commitment text contains a prompt injection instructing the oracle to return "hit" regardless of the data. Real money, real JSON, real attack surface.

I ran it against GPT-5 and Gemini 2.5 Pro. Three trials each, for consistency.

Gemini: 87% strict verdict accuracy. GPT-5: 77%.

That's the headline. Now the part that matters.

**Neither one is good enough.**

87% means thirteen settlements out of every hundred come back wrong. At a $100 average stake, that's $1,300 per 100 markets paid to the wrong side. Even if you squint and declare the errors "acceptable," you still have a market that refuses to clear on 13% of contracts. Nobody stakes money against a judge that's wrong one time in eight.

The more interesting signal is _calibration_ — not "did the model get it right" but "when the model is wrong, does it at least know it might be wrong?"

I built cases where the correct answer is literally _ambiguous_: data gaps on days where the user didn't wear the strap, commitments phrased with escape hatches like "or the equivalent", window boundaries where the counting rule is underspecified. A good oracle raises its hand. A bad oracle confidently guesses.

Gemini flagged ambiguity correctly 9 out of 10 times. GPT-5, 8 out of 10. Both consistent across trials. Both identified the data-quality concerns in their `flags` array — low strap wear, pending scoring state, duplicate records — in the _reasoning_, even when they got the verdict itself wrong.

This is the part that told me what to build.

Forget accuracy as the KPI. The real KPI is _refusal rate on actually-ambiguous cases_. An oracle that says "I cannot settle this safely, escalate to a human" is better than an oracle that guesses correctly 90% of the time, because the 10% silent failures are the ones that destroy trust.

Three things I'm taking from this into Keep:

**One: no free-form commitments, ever.** The commitment text is the highest-leverage attack surface. Users will get templates they can fill in — "hit [metric] [threshold] on [N] of the next [M] days" — and the oracle will only see structured commitment objects, never natural-language prose. Prompt injection has to be made structurally impossible, not merely unlikely.

**Two: data-quality gates before the oracle even reads the data.** If `scoring_state != "SCORED"` on any cycle in the window, settlement pauses. If `wearable_time_seconds < 18 hours` on more than one day, pause. If a cycle_id is missing from the expected sequence, pause. These are deterministic rules, not LLM judgment. The LLM only gets called on clean inputs.

**Three: two-model quorum with an explicit dissent-is-ambiguous rule.** One model is an oracle. Two agreeing models are a settlement. Disagreement means escalate. The marginal cost is a Gemini call at $0.004 per settlement. The marginal benefit is eliminating the 13% silent-failure tail.

Beeminder does the first part of this — constrained, structured commitments on top of a biometric API — and has been doing it for a decade. Their oracle is deterministic code. They don't need an LLM because they didn't need free-form phrasing.

I want Keep to look more like Beeminder than people expect. The LLM is the spell-check, not the judge. The judge is the rule.

Which is maybe the hidden lesson here. The prediction-market story about LLMs says "the oracle problem is solved, you just ask GPT-5." This weekend's eval says the opposite: the LLM makes the oracle problem _more_ interesting, because it gives you a way to refuse gracefully — which you never had before.

That's not the oracle being solved. That's the oracle being honest.

Settlement rules are laws. Laws with 87% accuracy aren't laws — they're vibes.

Tonight I'm designing Keep around the 13%.
