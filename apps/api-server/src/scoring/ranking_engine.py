"""
Root Cause Ranking Engine for SentinelOps Phase 10.

Instead of "highest confidence wins", this engine combines multiple
independent scoring dimensions into a final weighted rank.

Scoring dimensions:
    1. Evidence Coverage       — what fraction of anomalies does this hypothesis explain?
    2. Counterfactual Success  — do expected symptoms match observed symptoms?
    3. Historical Similarity   — how similar to previously confirmed incidents?
    4. Graph Consistency       — does the causal graph support this path?
    5. Repository Consistency  — do recent code changes align?
    6. Temporal Consistency     — does the timeline make sense?
    7. Hypothesis Stability    — is the confidence stable across evidence subsets?

Output:
    Ranked list of hypotheses with composite scores and per-dimension breakdown.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class DimensionScore:
    """Score for a single ranking dimension."""

    dimension: str
    score: float
    weight: float
    weighted_score: float
    rationale: str = ""


@dataclass
class RankedHypothesis:
    """A hypothesis with its composite ranking score and per-dimension breakdown."""

    hypothesis_id: str
    title: str
    composite_score: float
    rank: int
    dimension_scores: List[DimensionScore] = field(default_factory=list)
    confidence_label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "hypothesis_id": self.hypothesis_id,
            "title": self.title,
            "composite_score": self.composite_score,
            "confidence_label": self.confidence_label,
            "dimensions": {
                d.dimension: {"score": d.score, "weighted": d.weighted_score}
                for d in self.dimension_scores
            },
        }


# Default dimension weights (sum to 1.0)
_DEFAULT_DIMENSION_WEIGHTS: Dict[str, float] = {
    "evidence_coverage": 0.20,
    "counterfactual_success": 0.15,
    "historical_similarity": 0.15,
    "graph_consistency": 0.15,
    "repository_consistency": 0.10,
    "temporal_consistency": 0.15,
    "hypothesis_stability": 0.10,
}


def _confidence_label(score: float) -> str:
    if score >= 0.85:
        return "very_high"
    if score >= 0.70:
        return "high"
    if score >= 0.50:
        return "moderate"
    if score >= 0.30:
        return "low"
    return "very_low"


class RootCauseRankingEngine:
    """
    Multi-dimensional ranking engine for root cause hypotheses.

    Each hypothesis is scored independently across 7 dimensions,
    then a weighted composite determines the final rank order.
    """

    def __init__(
        self,
        dimension_weights: Dict[str, float] | None = None,
    ) -> None:
        self.weights = dimension_weights or dict(_DEFAULT_DIMENSION_WEIGHTS)

    def rank(
        self,
        candidates: List[Dict[str, Any]],
    ) -> List[RankedHypothesis]:
        """
        Rank a list of candidate hypotheses.

        Each candidate dict should contain:
            - hypothesis_id: str
            - title: str
            - evidence_coverage: float (0-1)
            - counterfactual_success: float (0-1)
            - historical_similarity: float (0-1)
            - graph_consistency: float (0-1)
            - repository_consistency: float (0-1)
            - temporal_consistency: float (0-1)
            - hypothesis_stability: float (0-1)
        """
        ranked: List[RankedHypothesis] = []

        for candidate in candidates:
            hid = candidate.get("hypothesis_id", "")
            title = candidate.get("title", "Unknown hypothesis")

            dimension_scores: List[DimensionScore] = []
            composite = 0.0

            for dim_name, weight in self.weights.items():
                raw_score = float(candidate.get(dim_name, 0.0))
                weighted = raw_score * weight
                composite += weighted

                dimension_scores.append(DimensionScore(
                    dimension=dim_name,
                    score=round(raw_score, 4),
                    weight=weight,
                    weighted_score=round(weighted, 4),
                ))

            ranked.append(RankedHypothesis(
                hypothesis_id=hid,
                title=title,
                composite_score=round(composite, 4),
                rank=0,  # Will be set after sorting
                dimension_scores=dimension_scores,
                confidence_label=_confidence_label(composite),
            ))

        # Sort by composite score descending and assign ranks
        ranked.sort(key=lambda h: h.composite_score, reverse=True)
        for i, hyp in enumerate(ranked):
            hyp.rank = i + 1

        return ranked

    def rank_from_candidates(
        self,
        candidates: Any,
        evidence_coverage_map: Dict[str, float] | None = None,
        counterfactual_map: Dict[str, float] | None = None,
        historical_map: Dict[str, float] | None = None,
        graph_map: Dict[str, float] | None = None,
        repo_map: Dict[str, float] | None = None,
        temporal_map: Dict[str, float] | None = None,
        stability_map: Dict[str, float] | None = None,
    ) -> List[RankedHypothesis]:
        """
        Convenience method to rank CandidateCause objects with external score maps.
        """
        ev_map = evidence_coverage_map or {}
        cf_map = counterfactual_map or {}
        hist_map = historical_map or {}
        g_map = graph_map or {}
        r_map = repo_map or {}
        t_map = temporal_map or {}
        s_map = stability_map or {}

        candidate_dicts = []
        for c in candidates:
            cid = getattr(c, "cause_id", "") or getattr(c, "pattern_id", "")
            title = getattr(c, "title", "") or getattr(c, "description", "")
            confidence = getattr(c, "confidence", 0.5)

            candidate_dicts.append({
                "hypothesis_id": cid,
                "title": title,
                "evidence_coverage": ev_map.get(
                    cid, getattr(c, "evidence_coverage", None) or confidence * 0.8
                ),
                "counterfactual_success": cf_map.get(cid, 0.5),
                "historical_similarity": hist_map.get(cid, 0.3),
                "graph_consistency": g_map.get(cid, confidence * 0.7),
                "repository_consistency": r_map.get(cid, 0.4),
                "temporal_consistency": t_map.get(cid, 0.5),
                "hypothesis_stability": s_map.get(cid, confidence),
            })

        return self.rank(candidate_dicts)
