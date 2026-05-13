from agents.uncertainty import UncertaintyIndicator
from pydantic import BaseModel, Field, model_validator


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
    evidence_quality: UncertaintyIndicator = Field(default_factory=UncertaintyIndicator.present)

    @model_validator(mode="after")
    def _assess_evidence_quality(self) -> "DeploymentSummary":
        if not self.recent_changes:
            self.evidence_quality = UncertaintyIndicator.unavailable(
                "no recent deployments found for service in the search window"
            )
            return self

        missing_sha = sum(1 for c in self.recent_changes if not c.commit_sha)
        if missing_sha == len(self.recent_changes):
            self.evidence_quality = UncertaintyIndicator.partial(
                "all deployment records lack commit SHA — provenance unverifiable",
                confidence=0.5,
            )
        elif missing_sha > 0:
            self.evidence_quality = UncertaintyIndicator.partial(
                f"{missing_sha}/{len(self.recent_changes)} deployment records lack commit SHA",
                confidence=0.7,
            )
        return self
