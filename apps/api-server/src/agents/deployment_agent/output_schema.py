from pydantic import BaseModel, Field


class RecentChange(BaseModel):
    deployment_id: str
    service: str
    version: str
    time: str
    commit_sha: str = ""
    commit_author: str = ""
    files_changed: list[str] = Field(default_factory=list)
    commit_summary: str
    risk_score: float = Field(ge=0.0, le=1.0)


class DeploymentSummary(BaseModel):
    recent_changes: list[RecentChange] = Field(default_factory=list)
    correlation_with_incident: str
