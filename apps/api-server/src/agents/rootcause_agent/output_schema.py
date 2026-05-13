from agents.uncertainty import ConfidenceInterval, EscalationDecision, UncertaintyAssessment
from pydantic import BaseModel, Field


class HypothesisEvidence(BaseModel):
    item_key: str
    description: str
    source: str


class RootCauseHypothesis(BaseModel):
    cause: str | None = None
    hypothesis: str
    cause_service: str
    affected_service: str
    evidence_for: list[HypothesisEvidence] = Field(default_factory=list)
    evidence_against: list[HypothesisEvidence] = Field(default_factory=list)
    evidence_neutral: list[HypothesisEvidence] = Field(default_factory=list)
    causal_chain: str
    counterfactual_test: str
    confidence: float | None = None
    calibrated_confidence: float | None = None
    probability: float | None = None
    rank: int | None = None
    contribution_weight: float | None = None
    temporal_score: float | None = None
    evidence_coverage: float | None = None
    pattern_match_score: float | None = None
    prior_probability: float | None = None
    counterfactual_power: float | None = None
    confidence_interval: ConfidenceInterval | None = None
    supporting_signals: list[str] = Field(default_factory=list)
    contradictory_signals: list[str] = Field(default_factory=list)


class RootCauseAnalysis(BaseModel):
    status: str
    hypotheses: list[RootCauseHypothesis] = Field(default_factory=list)
    strongest_hypothesis_index: int | None = None
    investigation_log: str
    recommended_next_steps: list[str] = Field(default_factory=list)
    uncertainty: UncertaintyAssessment | None = None
    escalation: EscalationDecision | None = None
    primary_state: str | None = None
    narrative: str = ""
    contributing_causes: list[str] = Field(default_factory=list)
    multi_cause: bool = False
