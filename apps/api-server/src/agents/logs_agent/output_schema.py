from pydantic import BaseModel, Field


class ErrorSignature(BaseModel):
    signature: str
    count: int
    first_seen: str
    sample: str
    trace_ids: list[str] = Field(default_factory=list)


class TemporalCorrelation(BaseModel):
    event: str
    timestamp: str
    relation: str


class LogsSummary(BaseModel):
    error_signatures: list[ErrorSignature] = Field(default_factory=list)
    temporal_correlations: list[TemporalCorrelation] = Field(default_factory=list)
