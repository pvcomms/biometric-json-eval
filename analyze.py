#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# ///
"""Post-process a run-*.json into a consistency + keep-decision analysis.

Groups results by (case, model), computes:
- majority verdict per model per case
- consistency rate (% trials agreeing with majority)
- strict-match accuracy (majority vs ground truth)
- disagreement cases (where different trials diverged)

For Keep: also computes oracle-safety score — does the model prefer 'ambiguous'
when the answer is genuinely ambiguous, or does it overconfidently call hit/miss?
"""

import json
import sys
from collections import Counter
from pathlib import Path


def load(path: str) -> dict:
    return json.loads(Path(path).read_text())


def majority(xs: list[str]) -> tuple[str, float]:
    if not xs:
        return "", 0.0
    c = Counter(xs)
    top, top_count = c.most_common(1)[0]
    return top, top_count / len(xs)


def analyze(data: dict) -> str:
    lines = []
    lines.append(f"# biometric-json-eval — consistency analysis\n")
    lines.append(f"_generated {data.get('generated_at','?')}_\n")

    per_model_stats: dict[str, dict] = {}
    per_case_disagreement = []

    for entry in data["results"]:
        case = entry["case"]
        gt = entry["expected_verdict"]
        grouped: dict[str, list] = {}
        for mr in entry["model_results"]:
            grouped.setdefault(mr["model"], []).append(mr)

        for model, trials in grouped.items():
            verdicts = [t.get("parsed_verdict", "") for t in trials]
            confs = [t.get("parsed_confidence", 0.0) for t in trials]
            scores = [t.get("scores", {}) for t in trials]

            maj, cons = majority(verdicts)
            match = maj == gt

            stats = per_model_stats.setdefault(model, {
                "cases": 0, "strict_hits": 0, "consistency_sum": 0.0,
                "total_trials": 0, "total_cost": 0.0, "judge_score_sum": 0.0,
                "judge_count": 0, "ambiguous_when_gt_decisive": 0,
                "decisive_when_gt_ambiguous": 0,
            })
            stats["cases"] += 1
            stats["total_trials"] += len(trials)
            if match:
                stats["strict_hits"] += 1
            stats["consistency_sum"] += cons
            stats["total_cost"] += sum(t.get("cost_usd", 0.0) for t in trials)
            for s in scores:
                if s and "error" not in s:
                    try:
                        v = sum([s["verdict_match"], s["reasoning_quality"],
                                 s["edge_case_awareness"], s["hallucination"]]) / 4
                        stats["judge_score_sum"] += v
                        stats["judge_count"] += 1
                    except Exception:
                        pass

            if gt == "ambiguous" and maj in {"hit", "miss"}:
                stats["decisive_when_gt_ambiguous"] += 1
            if gt in {"hit", "miss"} and maj == "ambiguous":
                stats["ambiguous_when_gt_decisive"] += 1

            if len(set(verdicts)) > 1:
                per_case_disagreement.append({
                    "case": case, "model": model, "gt": gt,
                    "verdicts": verdicts, "confidences": confs,
                })

    lines.append("## Per-model summary\n")
    lines.append("| Model | Strict acc | Consistency | Avg judge | Oracle-safety | Cost |")
    lines.append("|-------|------------|-------------|-----------|---------------|------|")
    model_short = {
        "claude-opus-4-7": "opus", "claude-sonnet-4-6": "sonnet",
        "claude-haiku-4-5-20251001": "haiku", "gpt-5": "gpt", "gemini-2.5-pro": "gemini",
    }
    for m, s in sorted(per_model_stats.items()):
        name = model_short.get(m, m)
        acc = f"{s['strict_hits']}/{s['cases']} ({100*s['strict_hits']/s['cases']:.0f}%)" if s['cases'] else "—"
        cons = f"{100*s['consistency_sum']/s['cases']:.0f}%" if s['cases'] else "—"
        judge = f"{s['judge_score_sum']/s['judge_count']:.1f}" if s['judge_count'] else "—"
        safety_bad = s["decisive_when_gt_ambiguous"] + s["ambiguous_when_gt_decisive"]
        safety = f"{s['cases'] - safety_bad}/{s['cases']} calibrated"
        cost = f"${s['total_cost']:.4f}"
        lines.append(f"| {name} | {acc} | {cons} | {judge} | {safety} | {cost} |")
    lines.append("")

    lines.append("## Oracle-safety breakdown\n")
    lines.append("_Errors where model verdict category (decisive vs ambiguous) differs from ground truth._\n")
    lines.append("| Model | Decisive when GT=ambiguous (dangerous) | Ambiguous when GT=decisive (safe-ish) |")
    lines.append("|-------|----------------------------------------|---------------------------------------|")
    for m, s in sorted(per_model_stats.items()):
        name = model_short.get(m, m)
        lines.append(f"| {name} | {s['decisive_when_gt_ambiguous']} | {s['ambiguous_when_gt_decisive']} |")
    lines.append("")

    if per_case_disagreement:
        lines.append("## Intra-model disagreements (trials diverged)\n")
        for d in per_case_disagreement:
            name = model_short.get(d["model"], d["model"])
            lines.append(f"- **{d['case']}** ({name}, GT={d['gt']}): trials = {d['verdicts']}")
        lines.append("")
    else:
        lines.append("## Intra-model disagreements\n_None — every model was self-consistent across trials._\n")

    return "\n".join(lines)


def main() -> int:
    if len(sys.argv) < 2:
        runs = sorted(Path(__file__).parent.glob("results/run-*.json"))
        if not runs:
            print("no run files found", file=sys.stderr)
            return 2
        path = str(runs[-1])
        print(f"[analyze] using latest: {path}", file=sys.stderr)
    else:
        path = sys.argv[1]
    data = load(path)
    out = analyze(data)
    md_path = Path(path).with_suffix(".analysis.md")
    md_path.write_text(out)
    print(out)
    print(f"\nWrote: {md_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
