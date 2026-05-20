"""Unified event types for the SentinelOps event bus."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class EventType(Enum):
    INCIDENT_CREATED = "incident.created"
    INCIDENT_UPDATED = "incident.updated"
    INCIDENT_RESOLVED = "incident.resolved"
    LOG_PATTERN_DETECTED = "log.pattern_detected"
    ANOMALY_SCORE_UPDATED = "anomaly.score_updated"
    AGENT_REASONING_STARTED = "agent.reasoning_started"
    AGENT_REASONING_COMPLETED = "agent.reasoning_completed"
    ROOT_CAUSE_CONFIRMED = "rootcause.confirmed"
    ROOT_CAUSE_REJECTED = "rootcause.rejected"
    REMEDIATION_PROPOSED = "remediation.proposed"
    REMEDIATION_APPROVED = "remediation.approved"
    REMEDIATION_REJECTED = "remediation.rejected"
    REMEDIATION_EXECUTED = "remediation.executed"
    ROLLBACK_TRIGGERED = "rollback.triggered"
    ESCALATION_REQUIRED = "escalation.required"
    EVIDENCE_COLLECTED = "evidence.collected"
    CONFIDENCE_UPDATED = "confidence.updated"
    TELEMETRY_GAP_DETECTED = "telemetry.gap_detected"


@dataclass
class Event:
    event_type: EventType
    timestamp: datetime
    source: str
    incident_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    correlation_id: str = ""
    causation_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "incident_id": self.incident_id,
            "payload": self.payload,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Event":
        return cls(
            event_type=EventType(data["event_type"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            source=data["source"],
            incident_id=data["incident_id"],
            payload=data.get("payload", {}),
            correlation_id=data.get("correlation_id", ""),
            causation_id=data.get("causation_id", ""),
        )
