"""
Execution Outcome Memory for SentinelOps Phase 46.

Stores and retrieves remediation execution outcomes, enabling the system
to remember which actions worked vs. caused harm in past incidents.

Tracked per outcome record:
  - remediation_class: what action class was executed
  - mechanism_id: inferred failure mechanism
  - incident_category: type of incident
  - success: did the remediation resolve the incident?
  - required_rollback: was the action reversed?
  - blast_radius_mismatch: was the predicted blast radius wrong?
  - operator_reversal: did an operator undo the action?
  - postmortem_correction: did the postmortem identify a better action?
  - escalation_was_necessary: was manual escalation required?
  - resolution_time_minutes: how long until the incident closed?

This memory is in-process and bounded; it does NOT use neural adaptation.
All influence on future reasoning is transparent and logged.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any


@dataclass
class OutcomeRecord:
    """Single remediation execution outcome with full provenance."""

    outcome_id: str
    incident_id: str
    remediation_class: str
    mechanism_id: str | None
    incident_category: str
    success: bool
    required_rollback: bool = False
    blast_radius_mismatch: bool = False
    operator_reversal: bool = False
    postmortem_correction: bool = False
    escalation_was_necessary: bool = False
    resolution_time_minutes: float | None = None
    predicted_blast_radius: int = 0
    actual_blast_radius: int = 0
    predicted_risk_score: float = 0.0
    actual_severity: str = ""
    execution_note: str = ""
    timestamp_iso: str = ""

    @property
    def was_harmful(self) -> bool:
        return self.required_rollback or self.operator_reversal

    @property
    def effectiveness_score(self) -> float:
        """0.0 = harmful, 1.0 = fully effective."""
        if self.was_harmful:
            return 0.0
        if not self.success:
            return 0.25
        if self.postmortem_correction:
            return 0.60
        if self.escalation_was_necessary:
            return 0.70
        return 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome_id": self.outcome_id,
            "incident_id": self.incident_id,
            "remediation_class": self.remediation_class,
            "mechanism_id": self.mechanism_id,
            "incident_category": self.incident_category,
            "success": self.success,
            "required_rollback": self.required_rollback,
            "blast_radius_mismatch": self.blast_radius_mismatch,
            "operator_reversal": self.operator_reversal,
            "postmortem_correction": self.postmortem_correction,
            "escalation_was_necessary": self.escalation_was_necessary,
            "resolution_time_minutes": self.resolution_time_minutes,
            "predicted_blast_radius": self.predicted_blast_radius,
            "actual_blast_radius": self.actual_blast_radius,
            "predicted_risk_score": round(self.predicted_risk_score, 4),
            "actual_severity": self.actual_severity,
            "was_harmful": self.was_harmful,
            "effectiveness_score": round(self.effectiveness_score, 4),
            "execution_note": self.execution_note,
            "timestamp_iso": self.timestamp_iso,
        }


@dataclass
class ReliabilityProfile:
    """Aggregate reliability statistics for a remediation class or mechanism."""

    key: str
    key_type: str  # "remediation_class" or "mechanism_id"
    total_executions: int
    success_count: int
    rollback_count: int
    reversal_count: int
    mean_effectiveness: float
    success_rate: float
    harm_rate: float
    reliability_score: float
    sample_size_warning: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "key_type": self.key_type,
            "total_executions": self.total_executions,
            "success_count": self.success_count,
            "rollback_count": self.rollback_count,
            "reversal_count": self.reversal_count,
            "mean_effectiveness": round(self.mean_effectiveness, 4),
            "success_rate": round(self.success_rate, 4),
            "harm_rate": round(self.harm_rate, 4),
            "reliability_score": round(self.reliability_score, 4),
            "sample_size_warning": self.sample_size_warning,
        }


class ExecutionOutcomeMemory:
    """
    Remembers remediation outcomes to inform future trust and risk decisions.

    Key question answered: "Which actions historically worked vs caused harm?"
    """

    _MIN_SAMPLE_FOR_CONFIDENCE = 5

    def __init__(self) -> None:
        self._records: list[OutcomeRecord] = []

    def store(self, record: OutcomeRecord) -> None:
        self._records.append(record)

    def all_records(self) -> list[OutcomeRecord]:
        return list(self._records)

    def records_for_remediation(self, remediation_class: str) -> list[OutcomeRecord]:
        return [r for r in self._records if r.remediation_class == remediation_class]

    def records_for_mechanism(self, mechanism_id: str) -> list[OutcomeRecord]:
        return [r for r in self._records if r.mechanism_id == mechanism_id]

    def records_for_category(self, incident_category: str) -> list[OutcomeRecord]:
        return [r for r in self._records if r.incident_category == incident_category]

    def records_for_mechanism_and_remediation(
        self, mechanism_id: str, remediation_class: str
    ) -> list[OutcomeRecord]:
        return [
            r
            for r in self._records
            if r.mechanism_id == mechanism_id and r.remediation_class == remediation_class
        ]

    def reliability_for_remediation(self, remediation_class: str) -> ReliabilityProfile:
        """Compute reliability statistics for a remediation class."""
        recs = self.records_for_remediation(remediation_class)
        return self._build_profile(remediation_class, "remediation_class", recs)

    def reliability_for_mechanism(self, mechanism_id: str) -> ReliabilityProfile:
        """Compute reliability statistics for a failure mechanism."""
        recs = self.records_for_mechanism(mechanism_id)
        return self._build_profile(mechanism_id, "mechanism_id", recs)

    def _build_profile(
        self, key: str, key_type: str, recs: list[OutcomeRecord]
    ) -> ReliabilityProfile:
        if not recs:
            return ReliabilityProfile(
                key=key,
                key_type=key_type,
                total_executions=0,
                success_count=0,
                rollback_count=0,
                reversal_count=0,
                mean_effectiveness=0.5,
                success_rate=0.5,
                harm_rate=0.0,
                reliability_score=0.5,
                sample_size_warning=True,
            )
        n = len(recs)
        successes = sum(1 for r in recs if r.success)
        rollbacks = sum(1 for r in recs if r.required_rollback)
        reversals = sum(1 for r in recs if r.operator_reversal)
        mean_eff = mean(r.effectiveness_score for r in recs)
        success_rate = successes / n
        harm_rate = (rollbacks + reversals) / n

        # Reliability score: weighted blend of success rate and non-harm rate
        reliability = 0.6 * success_rate + 0.4 * (1.0 - harm_rate)

        return ReliabilityProfile(
            key=key,
            key_type=key_type,
            total_executions=n,
            success_count=successes,
            rollback_count=rollbacks,
            reversal_count=reversals,
            mean_effectiveness=round(mean_eff, 4),
            success_rate=round(success_rate, 4),
            harm_rate=round(harm_rate, 4),
            reliability_score=round(reliability, 4),
            sample_size_warning=n < self._MIN_SAMPLE_FOR_CONFIDENCE,
        )

    def rollback_rate_for_remediation(self, remediation_class: str) -> float:
        """Return the fraction of executions that required rollback."""
        recs = self.records_for_remediation(remediation_class)
        if not recs:
            return 0.0
        return sum(1 for r in recs if r.required_rollback) / len(recs)

    def mean_effectiveness_for_mechanism_remediation(
        self, mechanism_id: str, remediation_class: str
    ) -> float:
        """Return mean effectiveness for a specific mechanism + remediation pairing."""
        recs = self.records_for_mechanism_and_remediation(mechanism_id, remediation_class)
        if not recs:
            return 0.5  # neutral prior
        return round(mean(r.effectiveness_score for r in recs), 4)

    def most_harmful_remediations(self, top_n: int = 5) -> list[tuple[str, float]]:
        """Return remediations sorted by harm rate descending."""
        classes = {r.remediation_class for r in self._records}
        rates = [
            (cls, self.rollback_rate_for_remediation(cls)) for cls in classes
        ]
        return sorted(rates, key=lambda x: x[1], reverse=True)[:top_n]

    def blast_radius_accuracy(self) -> float:
        """Fraction of outcomes where predicted blast radius was within 50% of actual."""
        recs = [
            r for r in self._records
            if r.predicted_blast_radius > 0 and r.actual_blast_radius > 0
        ]
        if not recs:
            return 1.0
        accurate = sum(
            1
            for r in recs
            if abs(r.predicted_blast_radius - r.actual_blast_radius) / r.actual_blast_radius
            <= 0.50
        )
        return round(accurate / len(recs), 4)
