import hashlib

from pydantic import BaseModel, Field, model_validator

from agents.uncertainty import UncertaintyIndicator


class ErrorSignature(BaseModel):
    signature: str
    count: int
    first_seen: str
    sample: str
    trace_ids: list[str] = Field(default_factory=list)
    fingerprint: str = ""

    @model_validator(mode="after")
    def _derive_fingerprint(self) -> "ErrorSignature":
        if not self.fingerprint and self.signature:
            self.fingerprint = hashlib.sha1(self.signature.encode()).hexdigest()[:12]
        return self


class TemporalCorrelation(BaseModel):
    event: str
    timestamp: str
    relation: str


class LogsSummary(BaseModel):
    error_signatures: list[ErrorSignature] = Field(default_factory=list)
    temporal_correlations: list[TemporalCorrelation] = Field(default_factory=list)
    evidence_quality: UncertaintyIndicator = Field(
        default_factory=UncertaintyIndicator.present
    )

    @model_validator(mode="after")
    def _deduplicate_and_assess_quality(self) -> "LogsSummary":
        seen: dict[str, ErrorSignature] = {}
        for sig in self.error_signatures:
            key = sig.fingerprint or sig.signature
            if key in seen:
                seen[key].count += sig.count
                seen[key].trace_ids = list(set(seen[key].trace_ids + sig.trace_ids))
            else:
                seen[key] = sig
        self.error_signatures = list(seen.values())

        if not self.error_signatures:
            self.evidence_quality = UncertaintyIndicator.unavailable(
                "no error signatures extracted from logs"
            )
        return self
