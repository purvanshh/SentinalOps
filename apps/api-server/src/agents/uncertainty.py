"""
Operational uncertainty modeling for SentinelOps agents.

Provides a shared UncertaintyIndicator type and helper functions that agents
use to represent the quality and completeness of the evidence they collected.
Explicit uncertainty prevents the LLM from filling evidence gaps with
fabricated data.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


UncertaintyStatus = Literal["present", "partial", "unavailable", "conflicting"]


class UncertaintyIndicator(BaseModel):
    """Describes the quality and completeness of an agent's evidence collection."""

    status: UncertaintyStatus
    reason: str = ""
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)

    @classmethod
    def present(cls) -> "UncertaintyIndicator":
        return cls(status="present", confidence=1.0)

    @classmethod
    def partial(cls, reason: str, confidence: float = 0.6) -> "UncertaintyIndicator":
        return cls(status="partial", reason=reason, confidence=confidence)

    @classmethod
    def unavailable(cls, reason: str) -> "UncertaintyIndicator":
        return cls(status="unavailable", reason=reason, confidence=0.0)

    @classmethod
    def conflicting(cls, reason: str, confidence: float = 0.4) -> "UncertaintyIndicator":
        return cls(status="conflicting", reason=reason, confidence=confidence)

    @property
    def is_actionable(self) -> bool:
        """Return True when evidence is sufficient to support a reasoning step."""
        return self.status in ("present", "partial") and self.confidence >= 0.3


def infer_uncertainty_from_items(items: list[dict]) -> UncertaintyIndicator:
    """
    Derive an UncertaintyIndicator from a list of normalised evidence items.

    Rules:
    - No items → unavailable
    - All items have uncertainty_status partial → partial
    - Any conflicting item present → conflicting
    - Otherwise → present, with confidence = mean of item confidences
    """
    if not items:
        return UncertaintyIndicator.unavailable("no evidence items produced by agent")

    statuses = [item.get("uncertainty_status", "present") for item in items]
    confidences = [float(item.get("confidence", 1.0)) for item in items]

    if "conflicting" in statuses:
        return UncertaintyIndicator.conflicting(
            "conflicting evidence items detected",
            confidence=sum(confidences) / len(confidences),
        )

    if all(s == "partial" for s in statuses):
        return UncertaintyIndicator.partial(
            "all evidence items have partial provenance",
            confidence=sum(confidences) / len(confidences),
        )

    if all(s == "unavailable" for s in statuses):
        return UncertaintyIndicator.unavailable("all evidence items are unavailable")

    mean_confidence = round(sum(confidences) / len(confidences), 3)
    if all(s in ("present", "partial") for s in statuses):
        if mean_confidence < 0.5:
            return UncertaintyIndicator.partial(
                "low mean confidence across evidence items",
                confidence=mean_confidence,
            )
        return UncertaintyIndicator(status="present", confidence=mean_confidence)

    return UncertaintyIndicator(
        status="partial",
        reason="mixed evidence quality",
        confidence=mean_confidence,
    )
