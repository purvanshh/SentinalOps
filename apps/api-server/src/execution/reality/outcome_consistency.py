"""
Outcome consistency checker for Phase 48 operational realism.

Validates that the declared remediation outcome is consistent with:
  - The post-remediation telemetry
  - The operator's own intervention record
  - The execution truth classification

Detects "looked fixed but wasn't" and remediation side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from execution.reality.execution_truth import ExecutionRealityState, ExecutionTruthRecord


class ConsistencyVerdict(str, Enum):
    CONSISTENT = "consistent"
    DECLARED_SUCCESS_BUT_DEGRADED = "declared_success_but_degraded"
    UNDECLARED_SIDE_EFFECTS = "undeclared_side_effects"
    OPERATOR_OVERRIDE_UNEXPLAINED = "operator_override_unexplained"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


@dataclass
class OutcomeConsistencyReport:
    verdict: ConsistencyVerdict
    declared_outcome: str
    actual_state: str
    inconsistencies: list[str]
    reliability_score: float  # 0.0–1.0: how trustworthy the declared outcome is

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "declared_outcome": self.declared_outcome,
            "actual_state": self.actual_state,
            "inconsistencies": self.inconsistencies,
            "reliability_score": round(self.reliability_score, 4),
        }


class OutcomeConsistencyChecker:
    """
    Checks whether the declared outcome of a remediation matches reality.

    Usage:
        checker = OutcomeConsistencyChecker()
        report = checker.check(
            declared_outcome="resolved",
            truth_record=truth_record,
            operator_overrides=["reject"],  # any REJECT actions post-remediation
        )
    """

    def check(
        self,
        declared_outcome: str,
        truth_record: ExecutionTruthRecord,
        operator_overrides: list[str] | None = None,
    ) -> OutcomeConsistencyReport:
        inconsistencies: list[str] = []
        overrides = operator_overrides or []

        # Case 1: declared success but truth says otherwise
        if declared_outcome in ("resolved", "success") and not truth_record.is_genuine_success:
            inconsistencies.append(
                f"declared '{declared_outcome}' but execution truth is '{truth_record.state.value}'"
            )

        # Case 2: operator rejected after declared success
        if declared_outcome in ("resolved", "success") and "reject" in overrides:
            inconsistencies.append("operator_rejected_after_declared_success")

        # Case 3: deceptive recovery not surfaced
        if truth_record.is_deceptive and declared_outcome in ("resolved", "success"):
            inconsistencies.append(
                f"deceptive recovery state '{truth_record.state.value}' masked as success"
            )

        # Case 4: operator override without explanation
        if "override" in overrides and not inconsistencies:
            inconsistencies.append("operator_override_without_explained_cause")

        # Determine verdict
        if not inconsistencies:
            if not truth_record:
                verdict = ConsistencyVerdict.INSUFFICIENT_EVIDENCE
                reliability = 0.50
            else:
                verdict = ConsistencyVerdict.CONSISTENT
                reliability = 0.90 - truth_record.confidence_penalty
        elif "declared_success_but_degraded" in " ".join(inconsistencies) or (
            declared_outcome in ("resolved", "success")
            and truth_record.state != ExecutionRealityState.VERIFIED_SUCCESS
        ):
            verdict = ConsistencyVerdict.DECLARED_SUCCESS_BUT_DEGRADED
            reliability = max(0.10, 0.50 - truth_record.confidence_penalty)
        elif any("side_effect" in s for s in inconsistencies):
            verdict = ConsistencyVerdict.UNDECLARED_SIDE_EFFECTS
            reliability = 0.40
        else:
            verdict = ConsistencyVerdict.DECLARED_SUCCESS_BUT_DEGRADED
            reliability = max(0.10, 0.40 - truth_record.confidence_penalty)

        return OutcomeConsistencyReport(
            verdict=verdict,
            declared_outcome=declared_outcome,
            actual_state=truth_record.state.value,
            inconsistencies=inconsistencies,
            reliability_score=round(max(0.0, reliability), 4),
        )
