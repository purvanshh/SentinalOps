from __future__ import annotations

from dataclasses import dataclass

from agents.rootcause_agent.causal_validator import is_valid_path, service_exists
from agents.rootcause_agent.evidence_builder import TimedEvent
from orchestration.state.topology_schema import ServiceNode


@dataclass(slots=True)
class CandidateCause:
    pattern_id: str
    title: str
    cause_service: str
    affected_service: str
    pattern_match_score: float
    required_keywords: list[str]
    supporting_item_keys: list[str]


def build_candidate_causes(
    *,
    service: str,
    events: list[TimedEvent],
    topology_graph: dict[str, ServiceNode],
    pattern_hints: list[dict],
) -> list[CandidateCause]:
    event_lookup = {event.item_key: event for event in events}
    candidates: list[CandidateCause] = []
    for pattern in pattern_hints:
        cause_service = pattern.get("cause_service") or service
        affected_service = pattern.get("effect_service") or service

        # Reject candidates that reference services not registered in the topology.
        # This is a hard hallucination boundary: we must not reason over infrastructure
        # that does not exist, even if a pattern hint names it.
        if topology_graph and not service_exists(cause_service, topology_graph):
            continue
        if topology_graph and not service_exists(affected_service, topology_graph):
            continue

        if not is_valid_path(cause_service, affected_service, topology_graph):
            continue

        supporting_keys = [
            item_key
            for item_key, event in event_lookup.items()
            if any(
                symptom.lower() in event.summary.lower()
                for symptom in pattern.get("symptoms", [])
            )
        ]
        candidates.append(
            CandidateCause(
                pattern_id=pattern.get("pattern_id", pattern.get("title", "unknown-pattern")),
                title=pattern.get("title", "Unknown pattern"),
                cause_service=cause_service,
                affected_service=affected_service,
                pattern_match_score=float(pattern.get("match_score", 0.0)),
                required_keywords=[symptom.lower() for symptom in pattern.get("symptoms", [])],
                supporting_item_keys=supporting_keys,
            )
        )

    if not candidates:
        candidates.append(
            CandidateCause(
                pattern_id="unknown_service_degradation",
                title="Unknown service degradation",
                cause_service=service,
                affected_service=service,
                pattern_match_score=0.2,
                required_keywords=[],
                supporting_item_keys=[event.item_key for event in events[:2]],
            )
        )
    return candidates
