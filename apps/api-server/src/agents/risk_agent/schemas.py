from pydantic import BaseModel, Field


class CurrentImpact(BaseModel):
    error_rate: float
    estimated_users_impacted_so_far: int
    trend: str


class UserRiskDistribution(BaseModel):
    mean: int
    p90: int
    description: str


class BlastRadius(BaseModel):
    affected_services: list[str] = Field(default_factory=list)
    users_at_risk: UserRiskDistribution


class RemediationRisk(BaseModel):
    action: str
    probability_of_success: float
    worst_case_impact: str
    risk_score: float
    recommendation: str


class RiskAssessment(BaseModel):
    current_impact: CurrentImpact
    blast_radius: BlastRadius
    remediation_risks: list[RemediationRisk] = Field(default_factory=list)
