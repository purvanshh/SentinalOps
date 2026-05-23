"""System State Engine — evolving incident memory with temporal reasoning."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from .events import Event, EventType


class IncidentPhase(Enum):
    DETECTED = "detected"
    TRIAGING = "triaging"
    INVESTIGATING = "investigating"
    ROOT_CAUSE_IDENTIFIED = "root_cause_identified"
    REMEDIATING = "remediating"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


@dataclass
class AgentVote:
    agent_name: str
    hypothesis: str
    confidence: float
    timestamp: datetime
    evidence_ids: list[str] = field(default_factory=list)


@dataclass
class TimelineEntry:
    timestamp: datetime
    event_type: EventType
    source: str
    summary: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class IncidentState:
    """Complete evolving state of an incident."""

    incident_id: str
    phase: IncidentPhase = IncidentPhase.DETECTED
    timeline: list[TimelineEntry] = field(default_factory=list)
    confidence: dict[str, float] = field(default_factory=dict)
    evidence_graph: dict[str, list[str]] = field(default_factory=dict)
    agent_votes: list[AgentVote] = field(default_factory=list)
    actions_taken: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def apply_event(self, event: Event) -> None:
        """Apply an event to evolve incident state."""
        self.timeline.append(
            TimelineEntry(
                timestamp=event.timestamp,
                event_type=event.event_type,
                source=event.source,
                summary=event.payload.get("summary", ""),
                metadata=event.payload,
            )
        )
        self.updated_at = event.timestamp
        self._transition_phase(event)

    def _transition_phase(self, event: Event) -> None:
        transitions: dict[EventType, IncidentPhase] = {
            EventType.INCIDENT_CREATED: IncidentPhase.DETECTED,
            EventType.AGENT_REASONING_STARTED: IncidentPhase.INVESTIGATING,
            EventType.ROOT_CAUSE_CONFIRMED: IncidentPhase.ROOT_CAUSE_IDENTIFIED,
            EventType.REMEDIATION_PROPOSED: IncidentPhase.REMEDIATING,
            EventType.REMEDIATION_APPROVED: IncidentPhase.EXECUTING,
            EventType.ESCALATION_REQUIRED: IncidentPhase.ESCALATED,
            EventType.INCIDENT_RESOLVED: IncidentPhase.RESOLVED,
        }
        if event.event_type in transitions:
            self.phase = transitions[event.event_type]

    def add_agent_vote(self, vote: AgentVote) -> None:
        self.agent_votes.append(vote)
        self.confidence[vote.agent_name] = vote.confidence

    def add_evidence(self, evidence_id: str, linked_to: list[str] | None = None) -> None:
        self.evidence_graph[evidence_id] = linked_to or []

    def get_consensus_confidence(self) -> float:
        if not self.confidence:
            return 0.0
        return sum(self.confidence.values()) / len(self.confidence)


class StateEngine:
    """Manages incident states and applies events to evolve them."""

    def __init__(self) -> None:
        self._states: dict[str, IncidentState] = {}

    def get_or_create(self, incident_id: str) -> IncidentState:
        if incident_id not in self._states:
            self._states[incident_id] = IncidentState(incident_id=incident_id)
        return self._states[incident_id]

    def apply_event(self, event: Event) -> IncidentState:
        state = self.get_or_create(event.incident_id)
        state.apply_event(event)
        return state

    def get_state(self, incident_id: str) -> IncidentState | None:
        return self._states.get(incident_id)

    def get_active_incidents(self) -> list[IncidentState]:
        return [s for s in self._states.values() if s.phase != IncidentPhase.RESOLVED]
