"""Smoke tests for the oracle — offline, no LLM calls.

Mocks primary + confirmation to test orchestration + gate logic.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import DataQualityGate, Oracle


def _fake_primary(verdict: str, confidence: float = 0.95):
    def fn(commitment, window, provider, data):
        return ({"verdict": verdict, "confidence": confidence, "reasoning": f"mocked {verdict}"}, 0.05)
    return fn


def _fake_confirm(verdict: str, confidence: float = 0.95):
    def fn(commitment, window, provider, data):
        return ({"verdict": verdict, "confidence": confidence, "reasoning": f"mocked {verdict}"}, 0.005)
    return fn


def test_both_agree_hit():
    o = Oracle(primary_fn=_fake_primary("hit"), confirmation_fn=_fake_confirm("hit"))
    v = o.settle(
        commitment="anything",
        window={"start": "2026-04-13T00:00:00Z", "end": "2026-04-19T23:59:59Z"},
        provider="whoop",
        data={"records": [
            {"cycle_id": i, "created_at": f"2026-04-{13+i}T05:00:00Z", "score_state": "SCORED", "score": {"recovery_score": 75}}
            for i in range(7)
        ]},
    )
    assert v.outcome == "settled_hit", v.outcome
    print("OK: both_agree_hit ->", v.outcome)


def test_disagreement_pauses():
    o = Oracle(primary_fn=_fake_primary("hit"), confirmation_fn=_fake_confirm("miss"))
    v = o.settle(
        commitment="anything",
        window={"start": "2026-04-13T00:00:00Z", "end": "2026-04-19T23:59:59Z"},
        provider="whoop",
        data={"records": [
            {"cycle_id": i, "created_at": f"2026-04-{13+i}T05:00:00Z", "score_state": "SCORED", "score": {"recovery_score": 75}}
            for i in range(7)
        ]},
    )
    assert v.outcome == "pause_for_review", v.outcome
    print("OK: disagreement_pauses ->", v.outcome, "|", v.reason)


def test_ambiguous_pauses():
    o = Oracle(primary_fn=_fake_primary("ambiguous"), confirmation_fn=_fake_confirm("hit"))
    v = o.settle(
        commitment="anything",
        window={"start": "2026-04-13T00:00:00Z", "end": "2026-04-19T23:59:59Z"},
        provider="whoop",
        data={"records": [
            {"cycle_id": i, "created_at": f"2026-04-{13+i}T05:00:00Z", "score_state": "SCORED", "score": {"recovery_score": 75}}
            for i in range(7)
        ]},
    )
    assert v.outcome == "pause_for_review", v.outcome
    print("OK: ambiguous_pauses ->", v.outcome, "|", v.reason)


def test_gate_catches_missing_day():
    # Case 04 from the eval — cycle_id gap on Apr 16.
    case = json.loads((Path(__file__).parent.parent / "cases" / "04_missing_day_whoop.json").read_text())
    o = Oracle(primary_fn=_fake_primary("hit"), confirmation_fn=_fake_confirm("hit"))
    v = o.settle(
        commitment=case["commitment"],
        window=case["window"],
        provider=case["provider"],
        data=case["data"],
    )
    assert v.outcome == "pause_for_review", v.outcome
    assert "gate" in v.reason, v.reason
    # Ensure LLMs were never called.
    assert v.primary_response is None
    print("OK: gate_catches_missing_day ->", v.outcome, "|", v.reason[:120])


def test_gate_catches_pending_scoring():
    case = json.loads((Path(__file__).parent.parent / "cases" / "14_pending_scoring_state.json").read_text())
    o = Oracle(primary_fn=_fake_primary("hit"), confirmation_fn=_fake_confirm("hit"))
    v = o.settle(
        commitment=case["commitment"],
        window=case["window"],
        provider=case["provider"],
        data=case["data"],
    )
    assert v.outcome == "pause_for_review", v.outcome
    assert "SCORED" in v.reason, v.reason
    print("OK: gate_catches_pending_scoring ->", v.outcome)


def test_gate_catches_duplicate_cycles():
    case = json.loads((Path(__file__).parent.parent / "cases" / "13_duplicate_cycles.json").read_text())
    o = Oracle(primary_fn=_fake_primary("hit"), confirmation_fn=_fake_confirm("hit"))
    v = o.settle(
        commitment=case["commitment"],
        window=case["window"],
        provider=case["provider"],
        data=case["data"],
    )
    assert v.outcome == "pause_for_review", v.outcome
    assert "duplicate" in v.reason.lower(), v.reason
    print("OK: gate_catches_duplicate_cycles ->", v.outcome)


if __name__ == "__main__":
    test_both_agree_hit()
    test_disagreement_pauses()
    test_ambiguous_pauses()
    test_gate_catches_missing_day()
    test_gate_catches_pending_scoring()
    test_gate_catches_duplicate_cycles()
    print("\nall tests passed.")
