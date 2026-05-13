"""
Execution truth model for Phase 48 operational realism.

Defines ExecutionRealityState — the ground-truth classification of whether
a remediation or rollback actually succeeded in the real system.

Real systems exhibit:
  VERIFIED_SUCCESS    — telemetry confirms sustained recovery
  TEMPORARY_RECOVERY  — metrics improved briefly then regressed
  FALSE_RECOVERY      — signals looked good but underlying issue persisted
  PARTIAL_FAILURE     — some symptoms resolved, others did not
  HIDDEN_DEGRADATION  — system appears healthy but slowly degrading
  ROLLBACK_COLLAPSE   — rollback itself caused additional failures
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ExecutionRealityState(str, Enum):
    VERIFIED_SUCCESS = "verified_success"
    TEMPORARY_RECOVERY = "temporary_recovery"
    FALSE_RECOVERY = "false_recovery"
    PARTIAL_FAILURE = "partial_failure"
    HIDDEN_DEGRADATION = "hidden_degradation"
    ROLLBACK_COLLAPSE = "rollback_collapse"


_STATE_CONFIDENCE_PENALTY: dict[ExecutionRealityState, float] = {
    ExecutionRealityState.VERIFIED_SUCCESS: 0.0,
    ExecutionRealityState.TEMPORARY_RECOVERY: 0.15,
    ExecutionRealityState.FALSE_RECOVERY: 0.30,
    ExecutionRealityState.PARTIAL_FAILURE: 0.20,
    ExecutionRealityState.HIDDEN_DEGRADATION: 0.25,
    ExecutionRealityState.ROLLBACK_COLLAPSE: 0.40,
}


@dataclass
class ExecutionTruthRecord:
    """Tracks the actual outcome of a remediation execution."""

    incident_id: str
    remediation_id: str
    state: ExecutionRealityState
    evidence: list[str]
    confidence_penalty: float
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "remediation_id": self.remediation_id,
            "state": self.state.value,
            "evidence": self.evidence,
            "confidence_penalty": self.confidence_penalty,
            "notes": self.notes,
        }

    @property
    def is_genuine_success(self) -> bool:
        return self.state == ExecutionRealityState.VERIFIED_SUCCESS

    @property
    def is_deceptive(self) -> bool:
        return self.state in (
            ExecutionRealityState.FALSE_RECOVERY,
            ExecutionRealityState.HIDDEN_DEGRADATION,
        )


class ExecutionTruthClassifier:
    """
    Classifies the ground-truth outcome of a remediation based on post-remediation signals.

    Input: a sequence of metric snapshots taken at intervals after remediation.
    Each snapshot must have at least: {"timestamp_iso": ..., "error_rate": float}
    """

    _RECOVERY_THRESHOLD = 0.05  # error_rate < 5% = recovered
    _DEGRADATION_THRESHOLD = 0.20  # error_rate > 20% = degraded
    _OSCILLATION_COUNT = 2  # >2 direction changes = unstable

    def classify(
        self,
        incident_id: str,
        remediation_id: str,
        post_remediation_snapshots: list[dict[str, Any]],
    ) -> ExecutionTruthRecord:
        """
        Classify based on the post-remediation metric sequence.

        Expects snapshots sorted by time with an 'error_rate' field.
        """
        if not post_remediation_snapshots:
            return ExecutionTruthRecord(
                incident_id=incident_id,
                remediation_id=remediation_id,
                state=ExecutionRealityState.PARTIAL_FAILURE,
                evidence=["no_post_remediation_snapshots"],
                confidence_penalty=_STATE_CONFIDENCE_PENALTY[ExecutionRealityState.PARTIAL_FAILURE],
                notes="No post-remediation telemetry to verify outcome",
            )

        error_rates = [s.get("error_rate", 0.0) for s in post_remediation_snapshots]
        first = error_rates[0]
        last = error_rates[-1]

        # Count direction changes (oscillation detection)
        direction_changes = 0
        for i in range(1, len(error_rates)):
            prev_direction = error_rates[i - 1] - (error_rates[i - 2] if i > 1 else error_rates[0])
            curr_direction = error_rates[i] - error_rates[i - 1]
            if prev_direction * curr_direction < 0:
                direction_changes += 1

        evidence: list[str] = []

        # Verified success first: final rate sustained below recovery threshold
        if last <= self._RECOVERY_THRESHOLD and direction_changes < self._OSCILLATION_COUNT:
            evidence.append(f"sustained_recovery: final_error_rate={last:.2f}")
            state = ExecutionRealityState.VERIFIED_SUCCESS
        # Rollback collapse: error rate went UP substantially after remediation
        elif last > first + 0.10:
            evidence.append(f"error_rate_increased: {first:.2f}→{last:.2f}")
            state = ExecutionRealityState.ROLLBACK_COLLAPSE
        # False recovery: recovered briefly then regressed to degraded
        elif (
            any(r < self._RECOVERY_THRESHOLD for r in error_rates)
            and last > self._DEGRADATION_THRESHOLD
        ):
            evidence.append("brief_recovery_then_regression")
            state = ExecutionRealityState.FALSE_RECOVERY
        # Temporary recovery: oscillating
        elif direction_changes >= self._OSCILLATION_COUNT:
            evidence.append(f"oscillation_count={direction_changes}")
            state = ExecutionRealityState.TEMPORARY_RECOVERY
        # Hidden degradation: rate appears ok but slowly climbing
        elif last > first + 0.05 and last < self._DEGRADATION_THRESHOLD:
            evidence.append(f"slow_drift: {first:.2f}→{last:.2f}")
            state = ExecutionRealityState.HIDDEN_DEGRADATION
        # Partial failure: some snapshots above threshold but final is not recovered
        elif any(r > self._DEGRADATION_THRESHOLD for r in error_rates):
            evidence.append("intermittent_high_error_rate")
            state = ExecutionRealityState.PARTIAL_FAILURE
        else:
            state = ExecutionRealityState.PARTIAL_FAILURE
            evidence.append("ambiguous_recovery_signal")

        return ExecutionTruthRecord(
            incident_id=incident_id,
            remediation_id=remediation_id,
            state=state,
            evidence=evidence,
            confidence_penalty=_STATE_CONFIDENCE_PENALTY[state],
        )
