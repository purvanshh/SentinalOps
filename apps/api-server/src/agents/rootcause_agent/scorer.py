from __future__ import annotations

from agents.rootcause_agent.causal_validator import check_temporal_order
from agents.rootcause_agent.confidence import compute_confidence
from agents.rootcause_agent.deductive_tester import CandidateAssessment
from agents.rootcause_agent.evidence_builder import TimedEvent


def derive_prior_probability(incident_type: str | None, pattern_id: str) -> float:
    if not incident_type:
        return 0.4
    if incident_type in pattern_id:
        return 0.75
    if incident_type.replace("_", " ") in pattern_id.replace("_", " "):
        return 0.65
    return 0.45


def compute_temporal_score(events: list[TimedEvent]) -> float:
    serialized = [
        {
            "item_key": event.item_key,
            "timestamp": event.timestamp.isoformat() if event.timestamp else None,
        }
        for event in events
    ]
    return 1.0 if check_temporal_order(serialized) else 0.0


def score_assessment(
    assessment: CandidateAssessment, incident_type: str | None
) -> dict[str, float]:
    temporal_score = compute_temporal_score(assessment.evidence_for + assessment.evidence_neutral)
    prior_probability = derive_prior_probability(incident_type, assessment.candidate.pattern_id)
    confidence = compute_confidence(
        evidence_coverage=assessment.evidence_coverage,
        temporal_score=temporal_score,
        pattern_match_score=assessment.candidate.pattern_match_score,
        prior_probability=prior_probability,
        counterfactual_power=assessment.counterfactual_power,
    )
    return {
        "temporal_score": temporal_score,
        "prior_probability": prior_probability,
        "confidence": confidence,
    }
