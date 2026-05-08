from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from api.schemas.common import TimestampedResponse


class AlertPayload(BaseModel):
    title: str
    summary: str
    severity: str = Field(default="medium")
    source: str = Field(default="prometheus")
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class IncidentCreate(BaseModel):
    title: str
    severity: str
    source: str
    summary: str
    raw_payload: dict[str, Any]
    status: str = "open"


class AgentExecutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_name: str
    input: dict[str, Any] | None = None
    output: dict[str, Any] | None = None
    latency: float | None = None
    status: str
    created_at: datetime


class IncidentSummary(TimestampedResponse):
    title: str
    severity: str
    status: str
    source: str
    summary: str
    incident_type: str | None = None
    classification_confidence: float | None = None
    classification_rationale: str | None = None
    recommended_workflow: str | None = None


class IncidentResponse(IncidentSummary):
    raw_payload: dict[str, Any]
    agent_executions: list[AgentExecutionResponse] = Field(default_factory=list)
