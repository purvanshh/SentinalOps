"""
Retrieval hallucination suppression for SentinelOps.

Detects when LLM-generated claims are not grounded in retrieved evidence,
preventing the root cause agent from citing incidents it invented rather
than retrieved.

Key concepts:
  - A claim is "supported" if at least one retrieved result has a similarity
    score above the support threshold AND shares a keyword with the claim.
  - Claims with no supporting evidence are flagged as unsupported.
  - Results below the minimum grounding threshold are suppressed entirely.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from retrieval.provenance import GroundingStatus, _classify_grounding


_MIN_GROUNDING_SCORE = 0.45
_CLAIM_SUPPORT_THRESHOLD = 0.60
_STOPWORDS = frozenset({
    "the", "a", "an", "is", "was", "in", "on", "at", "to", "of", "and",
    "or", "for", "with", "that", "this", "it", "by", "from", "as", "be",
})


@dataclass
class UnsupportedClaim:
    """A claim that could not be grounded in retrieved evidence."""
    claim_text: str
    reason: str
    retrieved_count: int = 0
    max_similarity: float = 0.0


@dataclass
class ConsistencyReport:
    """Result of checking claim consistency against retrieved evidence."""
    supported_claims: list[str] = field(default_factory=list)
    unsupported_claims: list[UnsupportedClaim] = field(default_factory=list)
    suppressed_results: list[str] = field(default_factory=list)
    grounding_score: float = 0.0

    @property
    def is_trustworthy(self) -> bool:
        """True when no unsupported claims and grounding score is acceptable."""
        return not self.unsupported_claims and self.grounding_score >= _MIN_GROUNDING_SCORE

    @property
    def suppression_count(self) -> int:
        return len(self.suppressed_results)


def _extract_keywords(text: str) -> set[str]:
    """Extract meaningful lowercase words from text, excluding stopwords."""
    words = re.findall(r"[a-z][a-z0-9_-]*", text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}


def suppress_low_grounding_results(
    results: list[dict[str, Any]],
    *,
    min_score: float = _MIN_GROUNDING_SCORE,
) -> tuple[list[dict[str, Any]], list[str]]:
    """
    Filter out results whose similarity score is below min_score.

    Returns (kept_results, suppressed_incident_ids).
    """
    kept = []
    suppressed = []
    for result in results:
        prov = result.get("provenance") or {}
        score = float(
            prov.get("similarity_score")
            or result.get("match_score")
            or result.get("similarity_score")
            or 0.0
        )
        if score >= min_score:
            kept.append(result)
        else:
            incident_id = result.get("incident_id", result.get("id", "unknown"))
            suppressed.append(incident_id)
    return kept, suppressed


def check_claim_support(
    claim: str,
    results: list[dict[str, Any]],
    *,
    threshold: float = _CLAIM_SUPPORT_THRESHOLD,
) -> bool:
    """
    Return True if at least one result supports the claim.

    Support requires similarity score >= threshold AND at least one shared
    keyword between the claim and the result's text fields.
    """
    claim_keywords = _extract_keywords(claim)
    if not claim_keywords:
        return False

    for result in results:
        prov = result.get("provenance") or {}
        score = float(
            prov.get("similarity_score")
            or result.get("match_score")
            or result.get("similarity_score")
            or 0.0
        )
        if score < threshold:
            continue
        result_text = " ".join(str(v) for v in [
            result.get("title", ""),
            result.get("description", ""),
            result.get("summary", ""),
            result.get("root_cause", ""),
            " ".join(result.get("symptoms", [])),
        ])
        result_keywords = _extract_keywords(result_text)
        if claim_keywords & result_keywords:
            return True
    return False


def run_consistency_check(
    claims: list[str],
    results: list[dict[str, Any]],
    *,
    min_grounding_score: float = _MIN_GROUNDING_SCORE,
    claim_support_threshold: float = _CLAIM_SUPPORT_THRESHOLD,
) -> ConsistencyReport:
    """
    Check each claim against the retrieved results for grounding support.

    Suppresses results below min_grounding_score first, then verifies each
    claim against the remaining evidence.
    """
    kept, suppressed_ids = suppress_low_grounding_results(results, min_score=min_grounding_score)

    scores = []
    for r in kept:
        prov = r.get("provenance") or {}
        s = float(prov.get("similarity_score") or r.get("match_score") or 0.0)
        scores.append(s)
    grounding_score = round(sum(scores) / len(scores), 4) if scores else 0.0

    supported = []
    unsupported = []
    for claim in claims:
        if check_claim_support(claim, kept, threshold=claim_support_threshold):
            supported.append(claim)
        else:
            max_sim = max(
                (float((r.get("provenance") or {}).get("similarity_score") or r.get("match_score") or 0.0)
                 for r in results),
                default=0.0,
            )
            unsupported.append(UnsupportedClaim(
                claim_text=claim,
                reason="no retrieved result supports this claim with sufficient similarity",
                retrieved_count=len(results),
                max_similarity=round(max_sim, 4),
            ))

    return ConsistencyReport(
        supported_claims=supported,
        unsupported_claims=unsupported,
        suppressed_results=suppressed_ids,
        grounding_score=grounding_score,
    )
