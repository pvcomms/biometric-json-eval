"""Deterministic data-quality gate — runs before the LLM oracle.

Purpose: eliminate obvious data problems (missing cycles, unscored state, low
strap wear) with deterministic rules so the LLM only sees clean inputs. This
is the single highest-leverage safety mechanism identified in the overnight
eval — a "strict-v2" prompt that tried to move these checks into the LLM
regressed dangerous errors 0 -> 5. Keep them deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


MIN_WEARABLE_SECONDS_PER_DAY = 18 * 60 * 60  # 18 hours


@dataclass
class GateResult:
    passed: bool
    reasons: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class DataQualityGate:
    """Runs deterministic checks on a Whoop/Oura payload for a commitment window.

    Each check returns a list of failure reasons (empty == pass). A single
    failure from any check fails the gate; settlement pauses and the user
    is asked to attest or provide missing data.
    """

    def __init__(self, min_wearable_seconds: int = MIN_WEARABLE_SECONDS_PER_DAY):
        self.min_wearable_seconds = min_wearable_seconds

    def check(
        self,
        provider: str,
        data: dict,
        window_start: str,
        window_end: str,
        allowed_commitment_templates: list[str] | None = None,
        commitment_template_id: str | None = None,
    ) -> GateResult:
        reasons: list[str] = []
        metadata: dict = {}

        # 1. commitment must match a pre-approved template id.
        if allowed_commitment_templates is not None:
            if commitment_template_id not in allowed_commitment_templates:
                reasons.append(
                    f"commitment_template_id {commitment_template_id!r} not in "
                    f"whitelist {allowed_commitment_templates}"
                )

        records = self._extract_records(provider, data)
        metadata["record_count"] = len(records)

        # 2. every record must have scoring_state == "SCORED".
        unscored = [
            r for r in records
            if r.get("scoring_state") and r["scoring_state"] != "SCORED"
            or r.get("score_state") and r["score_state"] != "SCORED"
        ]
        if unscored:
            reasons.append(
                f"{len(unscored)} record(s) not yet SCORED "
                f"(states: {sorted({r.get('scoring_state') or r.get('score_state') for r in unscored})})"
            )

        # 3. no duplicate cycle_ids within the record set (oracle should see deduped).
        cycle_ids = [r.get("cycle_id") or r.get("id") for r in records if r.get("cycle_id") or r.get("id")]
        dupes = [cid for cid in set(cycle_ids) if cycle_ids.count(cid) > 1]
        if dupes:
            reasons.append(f"duplicate cycle_ids not deduplicated: {dupes[:5]}")

        # 4. every day in window has at least one record (no gaps).
        gaps = self._find_day_gaps(records, window_start, window_end)
        if gaps:
            reasons.append(f"days with no record in window: {gaps[:5]}")
            metadata["missing_days"] = gaps

        # 5. wearable_time_seconds (where present) must be above threshold per day.
        low_wear = [
            r for r in records
            if "wearable_time_seconds" in r.get("score", {})
            and r["score"]["wearable_time_seconds"] < self.min_wearable_seconds
        ]
        if low_wear:
            reasons.append(
                f"{len(low_wear)} record(s) with wearable_time_seconds < "
                f"{self.min_wearable_seconds} (18h)"
            )

        # 6. no null metric values in records we'll count.
        null_metric_records = [
            r for r in records
            if r.get("score", {}).get("recovery_score") is None
            and r.get("score_state") == "SCORED"
        ]
        if null_metric_records:
            reasons.append(f"{len(null_metric_records)} record(s) with null recovery_score despite SCORED state")

        return GateResult(passed=not reasons, reasons=reasons, metadata=metadata)

    def _extract_records(self, provider: str, data: dict) -> list[dict]:
        """Normalize both Whoop and Oura shapes into a list of record dicts."""
        if provider == "whoop":
            return list(data.get("records", []) + data.get("recovery", []) + data.get("cycles", []))
        if provider == "oura":
            return list(data.get("data", []))
        return []

    def _find_day_gaps(self, records: list[dict], start: str, end: str) -> list[str]:
        """Return ISO date strings (YYYY-MM-DD) inside [start, end] with no record."""
        try:
            s = datetime.fromisoformat(start.replace("Z", "+00:00")).astimezone(timezone.utc).date()
            e = datetime.fromisoformat(end.replace("Z", "+00:00")).astimezone(timezone.utc).date()
        except Exception:
            return []

        present: set = set()
        for r in records:
            for key in ("created_at", "start", "day"):
                v = r.get(key)
                if not v:
                    continue
                try:
                    if "T" in v:
                        d = datetime.fromisoformat(v.replace("Z", "+00:00")).astimezone(timezone.utc).date()
                    else:
                        d = datetime.fromisoformat(v).date()
                    present.add(d.isoformat())
                except Exception:
                    pass

        gaps = []
        cur = s
        while cur <= e:
            if cur.isoformat() not in present:
                gaps.append(cur.isoformat())
            cur = cur.fromordinal(cur.toordinal() + 1)
        return gaps
