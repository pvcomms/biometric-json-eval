#!/usr/bin/env bash
# Full eval sweep: default prompt + strict prompt on all cases, 3 trials, then analysis.
set -euo pipefail

cd "$(dirname "$0")"
source ~/.config/inbox-triage.env

MODELS="${MODELS:-gpt,gemini}"
TRIALS="${TRIALS:-3}"

echo "==> sweep: $MODELS x $TRIALS trials x both prompts"

echo "==> default prompt"
./eval.py --only "$MODELS" --trials "$TRIALS" --prompt default 2>&1 | tee results/latest-default.log | tail -20

echo "==> strict prompt"
./eval.py --only "$MODELS" --trials "$TRIALS" --prompt strict 2>&1 | tee results/latest-strict.log | tail -20

echo "==> analyses"
LATEST_DEFAULT=$(ls -t results/run-*-default*.json 2>/dev/null | head -1 || ls -t results/run-*.json | grep -v -- '-strict' | head -1)
LATEST_STRICT=$(ls -t results/run-*-strict*.json | head -1)
./analyze.py "$LATEST_DEFAULT" > results/latest-default.analysis.md
./analyze.py "$LATEST_STRICT" > results/latest-strict.analysis.md

echo "==> done. see results/latest-*.analysis.md"
