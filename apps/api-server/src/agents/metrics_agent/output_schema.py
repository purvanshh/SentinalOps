from agents.uncertainty import UncertaintyIndicator
from pydantic import BaseModel, Field, model_validator


class MetricAnomaly(BaseModel):
    metric: str
    observed: str
    expected_range: str
    z_score: float


class MetricsSummary(BaseModel):
    summary: str
    anomalies: list[MetricAnomaly] = Field(default_factory=list)
    correlation_hints: list[str] = Field(default_factory=list)
    raw_query_links: list[str] = Field(default_factory=list)
    evidence_quality: UncertaintyIndicator = Field(default_factory=UncertaintyIndicator.present)

    @model_validator(mode="after")
    def _assess_evidence_quality(self) -> "MetricsSummary":
        if not self.anomalies:
            self.evidence_quality = UncertaintyIndicator.partial(
                "no metric anomalies detected; summary may reflect insufficient telemetry",
                confidence=0.4,
            )
        return self
