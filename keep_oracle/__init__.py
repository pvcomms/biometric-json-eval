"""Keep settlement oracle — 3-stage stack from biometric-json-eval findings.

Stage 1: Deterministic data-quality gate (rule-based, no LLM).
Stage 2: Opus 4.7 strict-prompt primary oracle.
Stage 3: Gemini 2.5 Pro strict-prompt cross-provider confirmation.

Disagreement or either-ambiguous escalates to human review.

See ../FINDINGS.md for the empirical basis.
"""

from .oracle import Oracle, Verdict, GateResult
from .gate import DataQualityGate

__all__ = ["Oracle", "Verdict", "GateResult", "DataQualityGate"]
