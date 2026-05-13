"""
Lightweight mock objects implementing the Incident/AgentExecution interface.

These are used during evaluation to pass into real agent functions without
requiring a live database session. They satisfy the duck-typing requirements
of the agent functions (title, summary, severity, raw_payload, etc.) without
instantiating SQLAlchemy-mapped models.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from evaluation.benchmark_suite import BenchmarkIncident


@dataclass
class MockAgentExecution:
    """Duck-type replacement for db.models.agent_execution.AgentExecution."""

    agent_name: str
    output: dict[str, Any]
    input: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "completed"
    latency: float | None = None


@dataclass
class MockEvidenceItem:
    """Duck-type replacement for db.models.evidence.EvidenceItem."""

    item_key: str
    source: str
    item_type: str
    content: dict[str, Any]


@dataclass
class MockIncident:
    """
    Duck-type replacement for db.models.incident.Incident.

    Agents access: title, summary, severity, source, raw_payload, id,
    incident_type, classification_confidence, agent_executions.
    All other Incident fields are unused by the agent functions we invoke
    in evaluation mode.
    """

    title: str
    summary: str
    severity: str
    source: str
    raw_payload: dict[str, Any]
    id: UUID = field(default_factory=uuid4)
    incident_type: str | None = None
    classification_confidence: float | None = None
    agent_executions: list[MockAgentExecution] = field(default_factory=list)


def build_mock_incident_from_benchmark(benchmark: "BenchmarkIncident") -> MockIncident:
    """
    Build a MockIncident from a BenchmarkIncident.

    Only uses alert_payload and metadata fields — golden labels are
    never read here.
    """
    payload = benchmark.alert_payload
    return MockIncident(
        title=payload.get("title", benchmark.name),
        summary=payload.get("summary", benchmark.description),
        severity=payload.get("severity", "medium"),
        source=payload.get("source", "prometheus"),
        raw_payload=payload,
    )
