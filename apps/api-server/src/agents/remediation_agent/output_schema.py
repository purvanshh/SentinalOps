from pydantic import BaseModel, Field


class RemediationStep(BaseModel):
    action: str
    requires_approval: bool = True
    rationale: str
    verification_metric: str
    priority: int = 1


class RemediationPlan(BaseModel):
    summary: str
    steps: list[RemediationStep] = Field(default_factory=list)
    verify_after_execution: bool = True
