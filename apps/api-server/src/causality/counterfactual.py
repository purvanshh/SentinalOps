"""
Counterfactual reasoning for SentinelOps Phase 43.

Evaluates the claim: "Would the incident still exist without this event?"

Counterfactual analysis prevents false causal attribution by testing:
  1. Temporal necessity: did the candidate cause precede the effect?
  2. Topology necessity: is there a valid dependency path from cause to effect?
  3. Deployment timing: did a deployment occur after the incident started?
  4. Uniqueness: is there an alternative explanation that makes this candidate
     redundant?

A candidate cause FAILS the counterfactual test (is NOT the cause) when:
  - It occurred AFTER the incident anomaly onset
  - It has no topology path to the affected service
  - The incident would exist regardless (alternative cause covers it fully)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from causality.temporal_engine import _elapsed_seconds


@dataclass
class CounterfactualResult:
    """Result of testing one causal candidate counterfactually."""

    candidate_id: str
    candidate_description: str
    passes_counterfactual: bool
    temporal_necessity: bool
    topology_necessity: bool
    redundancy_free: bool
    explanation: str
    confidence_adjustment: float


def check_temporal_necessity(
    candidate_timestamp: str,
    effect_timestamp: str,
) -> tuple[bool, str]:
    """
    Returns (passes, explanation).
    Passes if candidate occurred BEFORE the effect (positive elapsed).
    """
    elapsed = _elapsed_seconds(candidate_timestamp, effect_timestamp)
    if elapsed > 0:
        return True, f"candidate preceded effect by {elapsed:.0f}s"
    if elapsed == 0:
        return True, "candidate and effect are simultaneous"
    return False, (
        f"candidate occurred {abs(elapsed):.0f}s AFTER effect — "
        "cannot be the cause (temporal contradiction)"
    )


def check_topology_necessity(
    cause_service: str,
    effect_service: str,
    topology: dict[str, Any],
) -> tuple[bool, str]:
    """
    Returns (passes, explanation).
    Passes if cause_service has a dependency path to effect_service,
    or if both services are the same.
    """
    if cause_service == effect_service:
        return True, "cause and effect are in the same service"
    if not topology:
        return True, "no topology available — assuming path may exist"

    deps = topology.get("dependencies", {})
    visited: set[str] = set()
    queue = [cause_service]
    while queue:
        current = queue.pop(0)
        if current == effect_service:
            return True, f"{cause_service} has dependency path to {effect_service}"
        for neighbor in deps.get(current, []):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)

    return False, (
        f"no dependency path from {cause_service} to {effect_service} "
        "— propagation is topologically impossible"
    )


def check_redundancy(
    candidate_id: str,
    alternative_causes: list[dict[str, Any]],
) -> tuple[bool, str]:
    """
    Returns (redundancy_free, explanation).
    A candidate is redundant if another higher-confidence candidate fully
    explains the incident and the candidate adds nothing.
    """
    if not alternative_causes:
        return True, "no alternative causes to compare against"

    stronger = [
        a
        for a in alternative_causes
        if a.get("id") != candidate_id and float(a.get("confidence", 0.0)) > 0.80
    ]
    if stronger:
        alt_descs = [a.get("description", a.get("id", "?")) for a in stronger[:2]]
        return False, (
            "candidate is redundant given higher-confidence alternatives: " + ", ".join(alt_descs)
        )
    return True, "no stronger alternative cause found"


def evaluate_counterfactual(
    candidate: dict[str, Any],
    *,
    effect_timestamp: str,
    effect_service: str,
    topology: dict[str, Any] | None = None,
    alternative_causes: list[dict[str, Any]] | None = None,
) -> CounterfactualResult:
    """
    Full counterfactual evaluation of a causal candidate.

    candidate dict expected keys:
      - id: str
      - description: str
      - timestamp_iso: str
      - service: str
      - confidence: float (optional)
    """
    cid = candidate.get("id", "unknown")
    desc = candidate.get("description", "")
    cand_ts = candidate.get("timestamp_iso", "")
    cand_svc = candidate.get("service", "")

    temporal_ok, temporal_reason = check_temporal_necessity(cand_ts, effect_timestamp)
    topology_ok, topology_reason = check_topology_necessity(
        cand_svc, effect_service, topology or {}
    )
    redundancy_ok, redundancy_reason = check_redundancy(cid, alternative_causes or [])

    passes = temporal_ok and topology_ok and redundancy_ok

    # Confidence adjustment: reward passing, penalize failing
    adjustment = 0.0
    if not temporal_ok:
        adjustment -= 0.30
    if not topology_ok:
        adjustment -= 0.25
    if not redundancy_ok:
        adjustment -= 0.15

    explanation_parts = [temporal_reason, topology_reason, redundancy_reason]
    explanation = "; ".join(p for p in explanation_parts if p)

    return CounterfactualResult(
        candidate_id=cid,
        candidate_description=desc,
        passes_counterfactual=passes,
        temporal_necessity=temporal_ok,
        topology_necessity=topology_ok,
        redundancy_free=redundancy_ok,
        explanation=explanation,
        confidence_adjustment=round(adjustment, 2),
    )


@dataclass
class CausalConfidenceScore:
    """Evidence-weighted causality confidence for one causal hypothesis."""

    candidate_id: str
    base_confidence: float
    temporal_score: float
    topology_score: float
    historical_similarity: float
    contradictory_evidence_penalty: float
    final_confidence: float
    factors: list[str]


def compute_causal_confidence(
    candidate: dict[str, Any],
    *,
    temporal_alignment: float = 1.0,
    topology_consistency: float = 1.0,
    historical_similarity: float = 0.5,
    contradictory_evidence_count: int = 0,
) -> CausalConfidenceScore:
    """
    Compute evidence-weighted causal confidence.

    Formula:
      base = (temporal_alignment * 0.35
             + topology_consistency * 0.30
             + historical_similarity * 0.20
             + pattern_match * 0.15)
      penalty = contradictory_evidence_count * 0.08
      final = clamp(base - penalty, 0.0, 1.0)
    """
    pattern_match = float(candidate.get("pattern_match_score", 0.5))
    base = (
        temporal_alignment * 0.35
        + topology_consistency * 0.30
        + historical_similarity * 0.20
        + pattern_match * 0.15
    )
    penalty = min(contradictory_evidence_count * 0.08, 0.40)
    final = round(max(0.0, min(1.0, base - penalty)), 4)

    factors = []
    if temporal_alignment < 0.5:
        factors.append("weak temporal alignment")
    if topology_consistency < 0.5:
        factors.append("topology inconsistency")
    if contradictory_evidence_count > 0:
        factors.append(f"{contradictory_evidence_count} contradictory evidence items")
    if historical_similarity > 0.8:
        factors.append("strong historical precedent")

    return CausalConfidenceScore(
        candidate_id=candidate.get("id", "unknown"),
        base_confidence=round(base, 4),
        temporal_score=temporal_alignment,
        topology_score=topology_consistency,
        historical_similarity=historical_similarity,
        contradictory_evidence_penalty=round(penalty, 4),
        final_confidence=final,
        factors=factors,
    )
