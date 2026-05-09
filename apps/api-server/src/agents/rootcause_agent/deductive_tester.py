from __future__ import annotations

from dataclasses import dataclass

from agents.rootcause_agent.causal_graph import CandidateCause
from agents.rootcause_agent.evidence_builder import TimedEvent


@dataclass(slots=True)
class CandidateAssessment:
    candidate: CandidateCause
    evidence_for: list[TimedEvent]
    evidence_against: list[TimedEvent]
    evidence_neutral: list[TimedEvent]
    evidence_coverage: float
    counterfactual_power: float


def assess_candidate(candidate: CandidateCause, events: list[TimedEvent]) -> CandidateAssessment:
    evidence_for: list[TimedEvent] = []
    evidence_against: list[TimedEvent] = []
    evidence_neutral: list[TimedEvent] = []

    matched_keywords = 0
    for event in events:
        summary = event.summary.lower()
        if event.item_key in candidate.supporting_item_keys:
            evidence_for.append(event)
            continue
        if any(keyword in summary for keyword in candidate.required_keywords):
            evidence_for.append(event)
            matched_keywords += 1
        elif event.service == candidate.cause_service or event.service == candidate.affected_service:
            evidence_neutral.append(event)
        else:
            evidence_against.append(event)

    required_total = max(len(candidate.required_keywords), 1)
    evidence_coverage = min((len(evidence_for) + matched_keywords) / required_total, 1.0)
    counterfactual_power = 0.85 if evidence_against == [] else max(0.35, 1 - (len(evidence_against) / max(len(events), 1)))

    return CandidateAssessment(
        candidate=candidate,
        evidence_for=evidence_for,
        evidence_against=evidence_against[:2],
        evidence_neutral=evidence_neutral[:3],
        evidence_coverage=evidence_coverage,
        counterfactual_power=counterfactual_power,
    )
