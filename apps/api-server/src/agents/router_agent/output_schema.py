from pydantic import BaseModel, Field


class RouterOutput(BaseModel):
    incident_type: str
    severity: str
    confidence: float = Field(ge=0.0, le=1.0)
    requires_immediate_investigation: bool
    recommended_workflow: str
    rationale: str
