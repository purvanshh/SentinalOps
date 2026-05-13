"""
Topology-aware hybrid retrieval for SentinelOps root cause analysis.

Combines pattern-based retrieval with:
  - Service topology filtering (boost results from related services)
  - Temporal decay weighting (recent incidents rank higher)
  - Provenance-scored result merging
"""
from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

from retrieval.embeddings.pattern_searcher import PatternSearcher
from retrieval.provenance import RetrievalProvenance, attach_provenance, compute_grounding_score


_TOPOLOGY_NEIGHBOR_BOOST = 0.10
_TIME_DECAY_HALF_LIFE_DAYS = 90.0


def _time_decay_weight(retrieved_at: str) -> float:
    """Exponential time decay: 1.0 at retrieval time, 0.5 after half-life days."""
    if not retrieved_at:
        return 1.0
    try:
        ts = datetime.fromisoformat(retrieved_at)
        now = datetime.now(UTC)
        age_days = (now - ts).total_seconds() / 86400.0
        return math.exp(-math.log(2) * max(age_days, 0.0) / _TIME_DECAY_HALF_LIFE_DAYS)
    except (ValueError, TypeError):
        return 1.0


def _topology_neighbors(service: str, topology: dict[str, Any]) -> set[str]:
    """Return services directly upstream or downstream of service in topology."""
    deps = topology.get("dependencies", {})
    neighbors: set[str] = set()
    for src, targets in deps.items():
        if service in (targets if isinstance(targets, list) else []):
            neighbors.add(src)
    if service in deps:
        targets = deps[service]
        if isinstance(targets, list):
            neighbors.update(targets)
    return neighbors


def _compute_hybrid_score(
    result: dict[str, Any],
    *,
    service: str,
    topology: dict[str, Any] | None,
) -> float:
    """Combine similarity, topology neighbor boost, and time decay."""
    base = float(result.get("match_score") or result.get("similarity_score") or 0.0)
    prov = result.get("provenance") or {}
    retrieved_at = prov.get("retrieved_at") or result.get("retrieved_at", "")
    decay = _time_decay_weight(retrieved_at)

    boost = 0.0
    if topology and service:
        result_service = result.get("service", "")
        if result_service:
            neighbors = _topology_neighbors(service, topology)
            if result_service == service or result_service in neighbors:
                boost = _TOPOLOGY_NEIGHBOR_BOOST

    return round(base * decay + boost, 4)


class HybridRetriever:
    """
    Topology-aware retriever that re-ranks pattern results using service topology
    and temporal decay.

    Each result is enriched with:
      - 'provenance': grounding metadata from RetrievalProvenance
      - 'hybrid_score': combined similarity + topology boost + time decay
    """

    def __init__(self, *, pattern_searcher: PatternSearcher | None = None) -> None:
        self._patterns = pattern_searcher or PatternSearcher()

    def retrieve(
        self,
        query: str,
        *,
        service: str = "",
        topology: dict[str, Any] | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Retrieve pattern results and re-rank by hybrid score.

        Returns results sorted by 'hybrid_score' descending, capped at limit.
        """
        raw = self._patterns.search(query, limit=limit * 2)
        enriched = attach_provenance(raw, collection="pattern_search", query_text=query)

        scored = []
        for result in enriched:
            hybrid_score = _compute_hybrid_score(result, service=service, topology=topology)
            scored.append({**result, "hybrid_score": hybrid_score})

        scored.sort(key=lambda r: r["hybrid_score"], reverse=True)
        return scored[:limit]

    def grounding_score(self, results: list[dict[str, Any]]) -> float:
        """Aggregate retrieval grounding quality across hybrid results."""
        provenances = []
        for r in results:
            prov_dict = r.get("provenance") or {}
            score = float(prov_dict.get("similarity_score") or r.get("match_score") or 0.0)
            provenances.append(
                RetrievalProvenance(
                    incident_id=r.get("incident_id", ""),
                    similarity_score=score,
                    retrieval_reason=prov_dict.get("retrieval_reason", ""),
                    matched_dimensions=prov_dict.get("matched_dimensions", []),
                    embedding_model=prov_dict.get("embedding_model", "unknown"),
                )
            )
        return compute_grounding_score(provenances)
