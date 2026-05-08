from pydantic import BaseModel, Field


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
