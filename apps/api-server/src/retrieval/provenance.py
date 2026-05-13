"""
Retrieval provenance model for SentinelOps.

RetrievalProvenance is the canonical record of WHY a historical item was
retrieved and HOW confident the retrieval system is. It is attached to every
item that enters agent reasoning so that:

  1. Operators can audit WHY the root cause agent cited a historical incident.
  2. Hallucination detectors can check that claims are grounded in retrieved
     evidence rather than invented by the LLM.
  3. Evaluation can measure retrieval quality across benchmark replays.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

GroundingStatus = Literal["grounded", "weakly_grounded", "ungrounded"]


@dataclass
class RetrievalProvenance:
    """Full provenance record for a single retrieved item."""

    incident_id: str
    similarity_score: float
    retrieval_reason: str
    matched_dimensions: list[str]
    embedding_model: str
    retrieved_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    collection: str = ""
    query_text: str = ""
    grounding_status: GroundingStatus = field(init=False)

    def __post_init__(self) -> None:
        self.grounding_status = _classify_grounding(self.similarity_score)

    @property
    def is_reliable(self) -> bool:
        """True when similarity score is high enough to ground a reasoning claim."""
        return self.similarity_score >= 0.70

    @property
    def is_actionable(self) -> bool:
        """True when this provenance can be cited in remediation suggestions."""
        return self.similarity_score >= 0.60 and self.grounding_status != "ungrounded"

    def to_dict(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "similarity_score": self.similarity_score,
            "retrieval_reason": self.retrieval_reason,
            "matched_dimensions": self.matched_dimensions,
            "embedding_model": self.embedding_model,
            "retrieved_at": self.retrieved_at,
            "collection": self.collection,
            "grounding_status": self.grounding_status,
            "is_reliable": self.is_reliable,
            "is_actionable": self.is_actionable,
        }

    @classmethod
    def from_retrieval_result(
        cls,
        result: dict[str, Any],
        *,
        collection: str = "",
        query_text: str = "",
    ) -> "RetrievalProvenance":
        score = float(result.get("similarity_score") or result.get("score") or 0.0)
        return cls(
            incident_id=result.get("incident_id", result.get("id", "")),
            similarity_score=round(score, 4),
            retrieval_reason=result.get("retrieval_reason", ""),
            matched_dimensions=result.get("matched_dimensions", []),
            embedding_model=result.get("embedding_model", "unknown"),
            retrieved_at=result.get("retrieved_at", datetime.now(UTC).isoformat()),
            collection=collection,
            query_text=query_text,
        )


def _classify_grounding(score: float) -> GroundingStatus:
    if score >= 0.70:
        return "grounded"
    if score >= 0.45:
        return "weakly_grounded"
    return "ungrounded"


def attach_provenance(
    results: list[dict[str, Any]],
    *,
    collection: str = "",
    query_text: str = "",
) -> list[dict[str, Any]]:
    """
    Enrich a list of retrieval results with a 'provenance' field.

    Each result gets a RetrievalProvenance built from its similarity_score,
    retrieval_reason, matched_dimensions, and embedding_model.
    """
    enriched = []
    for result in results:
        prov = RetrievalProvenance.from_retrieval_result(
            result,
            collection=collection,
            query_text=query_text,
        )
        enriched.append({**result, "provenance": prov.to_dict()})
    return enriched


def compute_grounding_score(provenances: list[RetrievalProvenance]) -> float:
    """
    Aggregate retrieval grounding quality across multiple provenances.

    Returns a score in [0, 1]:
      - 1.0: all items are fully grounded (>= 0.70 similarity)
      - 0.0: no items or all are ungrounded
    """
    if not provenances:
        return 0.0
    scores = [p.similarity_score for p in provenances]
    return round(sum(scores) / len(scores), 4)
