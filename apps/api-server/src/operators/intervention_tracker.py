"""
Operator intervention tracker for SentinelOps Phase 47.

Records operator actions during incident response and retrieves
them by incident, operator, or action kind for replay and analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class InterventionKind(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    OVERRIDE = "override"
    ESCALATE = "escalate"
    MANUAL_REMEDIATION = "manual_remediation"
    ACKNOWLEDGE = "acknowledge"
    COMMENT = "comment"
    ROLLBACK = "rollback"


@dataclass
class OperatorIntervention:
    """One recorded operator action during incident response."""

    intervention_id: str
    incident_id: str
    operator_id: str
    kind: InterventionKind
    timestamp_iso: str
    target_mechanism: str
    rationale: str = ""
    ai_recommendation: str = ""
    operator_action: str = ""
    confidence_at_time: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_override(self) -> bool:
        return self.kind in (InterventionKind.OVERRIDE, InterventionKind.REJECT)

    @property
    def is_approval(self) -> bool:
        return self.kind == InterventionKind.APPROVE

    @property
    def is_escalation(self) -> bool:
        return self.kind == InterventionKind.ESCALATE


@dataclass
class InterventionSummary:
    """Aggregated stats for a set of interventions."""

    total: int
    by_kind: dict[str, int]
    override_rate: float
    approval_rate: float
    escalation_rate: float
    unique_operators: int
    unique_incidents: int
    mean_confidence_at_intervention: float


class InterventionTracker:
    """
    In-process store of operator interventions.

    Supports lookup by incident, operator, and kind for downstream
    replay and analysis components.
    """

    def __init__(self) -> None:
        self._interventions: list[OperatorIntervention] = []

    def record(self, intervention: OperatorIntervention) -> None:
        self._interventions.append(intervention)

    def record_action(
        self,
        incident_id: str,
        operator_id: str,
        kind: InterventionKind | str,
        target_mechanism: str = "",
        rationale: str = "",
        ai_recommendation: str = "",
        operator_action: str = "",
        confidence_at_time: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> OperatorIntervention:
        if isinstance(kind, str):
            kind = InterventionKind(kind)
        iv_id = f"iv_{incident_id}_{len(self._interventions):05d}"
        ts = datetime.now(timezone.utc).isoformat()
        iv = OperatorIntervention(
            intervention_id=iv_id,
            incident_id=incident_id,
            operator_id=operator_id,
            kind=kind,
            timestamp_iso=ts,
            target_mechanism=target_mechanism,
            rationale=rationale,
            ai_recommendation=ai_recommendation,
            operator_action=operator_action,
            confidence_at_time=confidence_at_time,
            metadata=metadata or {},
        )
        self._interventions.append(iv)
        return iv

    def for_incident(self, incident_id: str) -> list[OperatorIntervention]:
        return [iv for iv in self._interventions if iv.incident_id == incident_id]

    def for_operator(self, operator_id: str) -> list[OperatorIntervention]:
        return [iv for iv in self._interventions if iv.operator_id == operator_id]

    def by_kind(self, kind: InterventionKind | str) -> list[OperatorIntervention]:
        if isinstance(kind, str):
            kind = InterventionKind(kind)
        return [iv for iv in self._interventions if iv.kind == kind]

    def overrides(self) -> list[OperatorIntervention]:
        return [iv for iv in self._interventions if iv.is_override]

    def approvals(self) -> list[OperatorIntervention]:
        return [iv for iv in self._interventions if iv.is_approval]

    def all_interventions(self) -> list[OperatorIntervention]:
        return list(self._interventions)

    def summarize(self) -> InterventionSummary:
        n = len(self._interventions)
        if n == 0:
            return InterventionSummary(
                total=0,
                by_kind={},
                override_rate=0.0,
                approval_rate=0.0,
                escalation_rate=0.0,
                unique_operators=0,
                unique_incidents=0,
                mean_confidence_at_intervention=0.0,
            )

        by_kind: dict[str, int] = {}
        for iv in self._interventions:
            by_kind[iv.kind.value] = by_kind.get(iv.kind.value, 0) + 1

        overrides = sum(1 for iv in self._interventions if iv.is_override)
        approvals = sum(1 for iv in self._interventions if iv.is_approval)
        escalations = sum(1 for iv in self._interventions if iv.is_escalation)
        mean_conf = sum(iv.confidence_at_time for iv in self._interventions) / n

        return InterventionSummary(
            total=n,
            by_kind=by_kind,
            override_rate=overrides / n,
            approval_rate=approvals / n,
            escalation_rate=escalations / n,
            unique_operators=len({iv.operator_id for iv in self._interventions}),
            unique_incidents=len({iv.incident_id for iv in self._interventions}),
            mean_confidence_at_intervention=mean_conf,
        )

    def clear(self) -> None:
        self._interventions.clear()
