from __future__ import annotations

from dataclasses import dataclass


@dataclass
class OperatorWorkflowState:
    active_incidents: list[str]
    fatigue_score: float
    confidence_in_system: float
    override_frequency: float
    escalation_pressure: float
    recent_false_positives: int
    cognitive_load: float


class WorkflowSimulator:
    _FATIGUE_PER_INCIDENT: float = 0.05
    _FATIGUE_UNRESOLVED_PENALTY: float = 0.10
    _FATIGUE_CONTEXT_SWITCH_PENALTY: float = 0.02
    _CONFIDENCE_DEGRADATION_PER_FP: float = 0.05
    _CONFIDENCE_FLOOR: float = 0.10
    _CONCURRENT_INCIDENT_THRESHOLD: int = 3

    def simulate_session(self, incidents: list[dict]) -> OperatorWorkflowState:
        fatigue: float = 0.0
        confidence: float = 1.0
        override_count: int = 0
        false_positive_count: int = 0
        context_switches: int = 0
        escalation_pressure: float = 0.0

        active_incidents: list[str] = []
        previous_incident_id: str | None = None

        for incident in incidents:
            incident_id: str = incident.get("id", "")
            is_resolved: bool = incident.get("resolved", True)
            is_false_positive: bool = incident.get("false_positive", False)
            is_override: bool = incident.get("override", False)

            if incident_id:
                active_incidents.append(incident_id)

            fatigue += self._FATIGUE_PER_INCIDENT

            if not is_resolved:
                fatigue += self._FATIGUE_UNRESOLVED_PENALTY

            if previous_incident_id is not None and previous_incident_id != incident_id:
                context_switches += 1
                fatigue += self._FATIGUE_CONTEXT_SWITCH_PENALTY

            concurrent_count = len(active_incidents)
            if concurrent_count > self._CONCURRENT_INCIDENT_THRESHOLD:
                excess = concurrent_count - self._CONCURRENT_INCIDENT_THRESHOLD
                escalation_pressure = min(1.0, escalation_pressure + 0.1 * excess)

            if is_false_positive:
                false_positive_count += 1
                confidence -= self._CONFIDENCE_DEGRADATION_PER_FP
                confidence = max(self._CONFIDENCE_FLOOR, confidence)

            if is_override:
                override_count += 1

            if is_resolved and incident_id in active_incidents:
                active_incidents.remove(incident_id)

            fatigue = min(1.0, fatigue)
            previous_incident_id = incident_id

        total_incidents = len(incidents)
        override_frequency: float = override_count / total_incidents if total_incidents > 0 else 0.0

        cognitive_load: float = min(
            1.0,
            0.4 * fatigue + 0.3 * escalation_pressure + 0.3 * override_frequency,
        )

        return OperatorWorkflowState(
            active_incidents=list(active_incidents),
            fatigue_score=fatigue,
            confidence_in_system=confidence,
            override_frequency=override_frequency,
            escalation_pressure=escalation_pressure,
            recent_false_positives=false_positive_count,
            cognitive_load=cognitive_load,
        )
