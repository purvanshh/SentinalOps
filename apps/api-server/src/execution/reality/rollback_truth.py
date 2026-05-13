"""
Rollback truth analysis for Phase 48 operational realism.

A rollback can fail in several ways:
  - Rollback loop: system rolls back to a version that also had the issue
  - Partial rollback: only some components were reverted
  - Rollback cascade: the rollback itself caused additional failures
  - False-positive rollback: rolled back a healthy change, didn't fix anything
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class RollbackOutcome(str, Enum):
    SUCCESSFUL = "successful"
    ROLLBACK_LOOP = "rollback_loop"
    PARTIAL_ROLLBACK = "partial_rollback"
    CASCADE_FAILURE = "cascade_failure"
    FALSE_POSITIVE = "false_positive"
    OSCILLATING = "oscillating"


@dataclass
class RollbackTruthRecord:
    rollback_id: str
    outcome: RollbackOutcome
    loop_count: int  # how many rollback iterations occurred
    components_rolled_back: list[str]
    components_still_affected: list[str]
    confidence_penalty: float
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "rollback_id": self.rollback_id,
            "outcome": self.outcome.value,
            "loop_count": self.loop_count,
            "components_rolled_back": self.components_rolled_back,
            "components_still_affected": self.components_still_affected,
            "confidence_penalty": round(self.confidence_penalty, 4),
            "description": self.description,
        }


_OUTCOME_PENALTY: dict[RollbackOutcome, float] = {
    RollbackOutcome.SUCCESSFUL: 0.0,
    RollbackOutcome.ROLLBACK_LOOP: 0.30,
    RollbackOutcome.PARTIAL_ROLLBACK: 0.15,
    RollbackOutcome.CASCADE_FAILURE: 0.35,
    RollbackOutcome.FALSE_POSITIVE: 0.20,
    RollbackOutcome.OSCILLATING: 0.25,
}


class RollbackTruthAnalyzer:
    """
    Determines the true outcome of a rollback sequence.

    A rollback sequence is a list of rollback attempt records, each with:
      {"version": str, "error_rate": float, "components": list[str], "success": bool}
    """

    def analyze(
        self,
        rollback_id: str,
        rollback_attempts: list[dict[str, Any]],
        affected_components: list[str] | None = None,
    ) -> RollbackTruthRecord:
        if not rollback_attempts:
            return RollbackTruthRecord(
                rollback_id=rollback_id,
                outcome=RollbackOutcome.PARTIAL_ROLLBACK,
                loop_count=0,
                components_rolled_back=[],
                components_still_affected=affected_components or [],
                confidence_penalty=_OUTCOME_PENALTY[RollbackOutcome.PARTIAL_ROLLBACK],
                description="No rollback attempts recorded",
            )

        loop_count = len(rollback_attempts)
        versions_seen = [a.get("version", "") for a in rollback_attempts]
        error_rates = [a.get("error_rate", 0.0) for a in rollback_attempts]
        final_rate = error_rates[-1]

        rolled_back = []
        for a in rollback_attempts:
            rolled_back.extend(a.get("components", []))
        components_rolled_back = list(set(rolled_back))
        still_affected = [c for c in (affected_components or []) if c not in components_rolled_back]

        # Rollback loop: same version appears more than once
        if len(versions_seen) != len(set(versions_seen)):
            return RollbackTruthRecord(
                rollback_id=rollback_id,
                outcome=RollbackOutcome.ROLLBACK_LOOP,
                loop_count=loop_count,
                components_rolled_back=components_rolled_back,
                components_still_affected=still_affected,
                confidence_penalty=_OUTCOME_PENALTY[RollbackOutcome.ROLLBACK_LOOP],
                description=f"Rollback loop detected across {loop_count} attempts",
            )

        # Cascade failure: error rate went up during rollback
        if final_rate > error_rates[0] + 0.10:
            return RollbackTruthRecord(
                rollback_id=rollback_id,
                outcome=RollbackOutcome.CASCADE_FAILURE,
                loop_count=loop_count,
                components_rolled_back=components_rolled_back,
                components_still_affected=still_affected,
                confidence_penalty=_OUTCOME_PENALTY[RollbackOutcome.CASCADE_FAILURE],
                description="Error rate increased after rollback — cascade failure",
            )

        # Oscillating: repeated ups and downs
        direction_changes = sum(
            1
            for i in range(2, len(error_rates))
            if (error_rates[i] - error_rates[i - 1]) * (error_rates[i - 1] - error_rates[i - 2]) < 0
        )
        if direction_changes >= 2:
            return RollbackTruthRecord(
                rollback_id=rollback_id,
                outcome=RollbackOutcome.OSCILLATING,
                loop_count=loop_count,
                components_rolled_back=components_rolled_back,
                components_still_affected=still_affected,
                confidence_penalty=_OUTCOME_PENALTY[RollbackOutcome.OSCILLATING],
                description=f"Oscillating recovery: {direction_changes} direction changes",
            )

        # Partial rollback: still affected components remain (higher priority than false-positive)
        if still_affected:
            return RollbackTruthRecord(
                rollback_id=rollback_id,
                outcome=RollbackOutcome.PARTIAL_ROLLBACK,
                loop_count=loop_count,
                components_rolled_back=components_rolled_back,
                components_still_affected=still_affected,
                confidence_penalty=_OUTCOME_PENALTY[RollbackOutcome.PARTIAL_ROLLBACK],
                description=f"Partial rollback: {len(still_affected)} components still affected",
            )

        # False positive: no components left affected but system was already healthy
        if error_rates[0] < 0.05 and final_rate < 0.05:
            return RollbackTruthRecord(
                rollback_id=rollback_id,
                outcome=RollbackOutcome.FALSE_POSITIVE,
                loop_count=loop_count,
                components_rolled_back=components_rolled_back,
                components_still_affected=[],
                confidence_penalty=_OUTCOME_PENALTY[RollbackOutcome.FALSE_POSITIVE],
                description="System was already healthy; rollback had no causal impact",
            )

        return RollbackTruthRecord(
            rollback_id=rollback_id,
            outcome=RollbackOutcome.SUCCESSFUL,
            loop_count=loop_count,
            components_rolled_back=components_rolled_back,
            components_still_affected=[],
            confidence_penalty=0.0,
            description="Rollback verified successful",
        )
