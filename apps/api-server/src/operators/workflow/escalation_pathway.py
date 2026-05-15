from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EscalationLevel(Enum):
    L1_AUTOMATED = 1
    L2_OPERATOR = 2
    L3_SENIOR_ONCALL = 3
    L4_INCIDENT_COMMANDER = 4
    L5_EXECUTIVE = 5


_LEVEL_ORDER: list[EscalationLevel] = [
    EscalationLevel.L1_AUTOMATED,
    EscalationLevel.L2_OPERATOR,
    EscalationLevel.L3_SENIOR_ONCALL,
    EscalationLevel.L4_INCIDENT_COMMANDER,
    EscalationLevel.L5_EXECUTIVE,
]

_LEVEL_INDEX: dict[EscalationLevel, int] = {lvl: i for i, lvl in enumerate(_LEVEL_ORDER)}


@dataclass
class EscalationStep:
    from_level: EscalationLevel
    to_level: EscalationLevel
    reason: str
    trigger: str
    elapsed_seconds: float


@dataclass
class EscalationPathway:
    incident_id: str
    steps: list[EscalationStep]
    current_level: EscalationLevel
    is_escalating: bool
    total_escalations: int


class EscalationChain:
    def __init__(self) -> None:
        self._pathways: dict[str, EscalationPathway] = {}

    def start_incident(self, incident_id: str) -> EscalationPathway:
        pathway = EscalationPathway(
            incident_id=incident_id,
            steps=[],
            current_level=EscalationLevel.L1_AUTOMATED,
            is_escalating=False,
            total_escalations=0,
        )
        self._pathways[incident_id] = pathway
        return pathway

    def _get(self, incident_id: str) -> EscalationPathway:
        pathway = self._pathways.get(incident_id)
        if pathway is None:
            raise KeyError(f"Incident not found: {incident_id}")
        return pathway

    def escalate(
        self,
        incident_id: str,
        reason: str,
        trigger: str,
        elapsed_seconds: float,
    ) -> EscalationStep:
        pathway = self._get(incident_id)
        current_index = _LEVEL_INDEX[pathway.current_level]
        next_index = min(current_index + 1, len(_LEVEL_ORDER) - 1)
        next_level = _LEVEL_ORDER[next_index]

        step = EscalationStep(
            from_level=pathway.current_level,
            to_level=next_level,
            reason=reason,
            trigger=trigger,
            elapsed_seconds=elapsed_seconds,
        )
        pathway.steps.append(step)
        pathway.current_level = next_level
        pathway.is_escalating = True
        pathway.total_escalations += 1
        return step

    def de_escalate(self, incident_id: str) -> None:
        pathway = self._get(incident_id)
        current_index = _LEVEL_INDEX[pathway.current_level]
        if current_index > _LEVEL_INDEX[EscalationLevel.L2_OPERATOR]:
            pathway.current_level = _LEVEL_ORDER[current_index - 1]
            pathway.is_escalating = False

    def get_pathway(self, incident_id: str) -> EscalationPathway:
        return self._get(incident_id)

    def escalation_summary(self) -> dict:
        if not self._pathways:
            return {
                "mean_escalations": 0.0,
                "max_level_reached": None,
                "escalation_spam_rate": 0.0,
            }

        pathways = list(self._pathways.values())
        total_escalations = [p.total_escalations for p in pathways]
        mean_escalations = sum(total_escalations) / len(total_escalations)

        max_level: EscalationLevel | None = None
        for pathway in pathways:
            if pathway.steps:
                highest = max(pathway.steps, key=lambda s: _LEVEL_INDEX[s.to_level])
                candidate = highest.to_level
            else:
                candidate = pathway.current_level
            if max_level is None or _LEVEL_INDEX[candidate] > _LEVEL_INDEX[max_level]:
                max_level = candidate

        spam_count = sum(1 for p in pathways if p.total_escalations > 2)
        escalation_spam_rate = spam_count / len(pathways)

        return {
            "mean_escalations": mean_escalations,
            "max_level_reached": max_level,
            "escalation_spam_rate": escalation_spam_rate,
        }
