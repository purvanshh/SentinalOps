"""Core domain schemas for SentinelOps."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class IncidentSchema:
    id: str
    title: str
    severity: str
    category: str
    timestamp: datetime
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvidenceSchema:
    id: str
    incident_id: str
    source: str
    content: str
    confidence: float
    timestamp: datetime


@dataclass
class RemediationSchema:
    id: str
    incident_id: str
    actions: list[str]
    risk_level: str
    requires_approval: bool
