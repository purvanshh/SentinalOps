from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ApprovalDecisionRequest(BaseModel):
    approved: bool
    note: str = ""


class ApprovalQueueItem(BaseModel):
    incident_id: UUID
    status: str
    summary: str
    actions: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: str


class ApprovalResponse(BaseModel):
    incident_id: UUID
    approved: bool
    status: str
    note: str = ""
