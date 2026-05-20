"""Data Transfer Objects for API boundaries."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class IncidentDTO:
    id: str
    title: str
    severity: str
    status: str
    created_at: datetime


@dataclass
class AgentResultDTO:
    agent_name: str
    result: dict[str, Any]
    confidence: float
    duration_ms: float


@dataclass
class EvaluationResultDTO:
    metric_name: str
    score: float
    details: dict[str, Any]
