#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "anthropic>=0.40",
#   "google-generativeai>=0.8",
# ]
# ///
"""CLI for the Keep settlement oracle. Loads a case file, runs the 3-stage stack,
prints the verdict + reasoning.

Usage:
  ./oracle_cli.py cases/01_clear_recovery_hit.json
  ./oracle_cli.py cases/04_missing_day_whoop.json   # should pause on gate
"""

import json
import os
import sys
from pathlib import Path


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.strip().strip("'").strip('"')
        os.environ.setdefault(k.strip(), v)


_load_env_file(Path.home() / ".config" / "inbox-triage.env")

sys.path.insert(0, str(Path(__file__).parent))
from keep_oracle import Oracle


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: oracle_cli.py <case_file.json>", file=sys.stderr)
        return 2

    case = json.loads(Path(sys.argv[1]).read_text())
    oracle = Oracle()

    print(f"# settling: {case['name']}")
    print(f"commitment: {case['commitment']}")
    print(f"window:     {case['window']['start']} -> {case['window']['end']}")
    print(f"provider:   {case['provider']}")
    print(f"expected:   {case['expected']['verdict']}")
    print()

    verdict = oracle.settle(
        commitment=case["commitment"],
        window=case["window"],
        provider=case["provider"],
        data=case["data"],
    )

    print(f"## outcome: {verdict.outcome}")
    print(f"reason: {verdict.reason}")
    print(f"cost:   ${verdict.cost_usd:.4f}")

    if verdict.gate and verdict.gate.reasons:
        print("\n### gate reasons")
        for r in verdict.gate.reasons:
            print(f"  - {r}")

    if verdict.primary_response:
        print("\n### primary (Opus 4.7)")
        print(f"  verdict:    {verdict.primary_response.get('verdict')}")
        print(f"  confidence: {verdict.primary_response.get('confidence')}")
        print(f"  reasoning:  {verdict.primary_response.get('reasoning','')[:200]}...")

    if verdict.confirmation_response:
        print("\n### confirmation (Gemini 2.5 Pro)")
        print(f"  verdict:    {verdict.confirmation_response.get('verdict')}")
        print(f"  confidence: {verdict.confirmation_response.get('confidence')}")
        print(f"  reasoning:  {verdict.confirmation_response.get('reasoning','')[:200]}...")

    return 0


if __name__ == "__main__":
    sys.exit(main())
