"""
Data models for SentinelOps Phase 47 telemetry replay.

Defines TelemetryEvent, ReplaySession, and timeline structures used
across the replay engine, timeline reconstructor, and event stream.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EventKind(str, Enum):
    METRIC = "metric"
    LOG = "log"
    DEPLOYMENT = "deployment"
    ALERT = "alert"
    OPERATOR_ACTION = "operator_action"
    REMEDIATION_ACTION = "remediation_action"
    TOPOLOGY_CHANGE = "topology_change"


class ReplayState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class TelemetryEvent:
    """A single telemetry event from any source."""

    event_id: str
    kind: EventKind
    timestamp_iso: str
    service: str
    payload: dict[str, Any]
    source: str = ""
    severity: str = "info"
    labels: dict[str, str] = field(default_factory=dict)
    incident_id: str | None = None
    sequence_number: int = 0

    def fingerprint(self) -> str:
        """Deterministic hash for deduplication and audit."""
        canonical = json.dumps(
            {
                "event_id": self.event_id,
                "kind": self.kind.value,
                "timestamp_iso": self.timestamp_iso,
                "service": self.service,
                "source": self.source,
            },
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "kind": self.kind.value,
            "timestamp_iso": self.timestamp_iso,
            "service": self.service,
            "payload": self.payload,
            "source": self.source,
            "severity": self.severity,
            "labels": self.labels,
            "incident_id": self.incident_id,
            "sequence_number": self.sequence_number,
            "fingerprint": self.fingerprint(),
        }


@dataclass
class ReplaySession:
    """Metadata for a single replay run."""

    session_id: str
    source_path: str
    total_events: int
    start_timestamp_iso: str
    end_timestamp_iso: str
    replay_speed: float = 1.0
    seed: int = 0
    state: ReplayState = ReplayState.IDLE
    events_replayed: int = 0
    session_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "source_path": self.source_path,
            "total_events": self.total_events,
            "start_timestamp_iso": self.start_timestamp_iso,
            "end_timestamp_iso": self.end_timestamp_iso,
            "replay_speed": self.replay_speed,
            "seed": self.seed,
            "state": self.state.value,
            "events_replayed": self.events_replayed,
            "session_hash": self.session_hash,
        }


@dataclass
class IncidentTimeline:
    """Reconstructed timeline for a single incident."""

    incident_id: str
    timeline: list[dict[str, Any]]
    critical_transitions: list[dict[str, Any]]
    operator_interventions: list[dict[str, Any]]
    causal_chain: list[dict[str, Any]]
    start_timestamp_iso: str
    end_timestamp_iso: str
    duration_seconds: float
    telemetry_completeness: float  # 0.0 = no telemetry, 1.0 = full coverage
    event_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "timeline": self.timeline,
            "critical_transitions": self.critical_transitions,
            "operator_interventions": self.operator_interventions,
            "causal_chain": self.causal_chain,
            "start_timestamp_iso": self.start_timestamp_iso,
            "end_timestamp_iso": self.end_timestamp_iso,
            "duration_seconds": round(self.duration_seconds, 2),
            "telemetry_completeness": round(self.telemetry_completeness, 4),
            "event_count": self.event_count,
        }
