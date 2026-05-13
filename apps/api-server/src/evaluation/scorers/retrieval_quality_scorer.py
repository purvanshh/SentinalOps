"""
Retrieval quality scorer for SentinelOps Phase 42 benchmark evaluation.

Measures four dimensions of semantic retrieval quality:
  - retrieval_precision: fraction of retrieved results that are relevant
  - retrieval_recall: fraction of known relevant incidents that were retrieved
  - retrieval_grounding_score: mean similarity across retrieved results
  - semantic_similarity_accuracy: fraction of results above the grounding threshold
"""
from __future__ import annotations

from typing import Any


_GROUNDING_THRESHOLD = 0.70


def score_retrieval_precision(
    retrieved_ids: list[str],
    relevant_ids: set[str],
) -> float:
    """Fraction of retrieved results that appear in the relevant set."""
    if not retrieved_ids:
        return 0.0
    hits = sum(1 for rid in retrieved_ids if rid in relevant_ids)
    return round(hits / len(retrieved_ids), 4)


def score_retrieval_recall(
    retrieved_ids: list[str],
    relevant_ids: set[str],
) -> float:
    """Fraction of known relevant incidents that were retrieved."""
    if not relevant_ids:
        return 1.0
    hits = sum(1 for rid in relevant_ids if rid in retrieved_ids)
    return round(hits / len(relevant_ids), 4)


def score_retrieval_grounding(results: list[dict[str, Any]]) -> float:
    """Mean similarity score across all retrieved results."""
    if not results:
        return 0.0
    scores = []
    for r in results:
        prov = r.get("provenance") or {}
        s = float(
            prov.get("similarity_score")
            or r.get("match_score")
            or r.get("similarity_score")
            or 0.0
        )
        scores.append(s)
    return round(sum(scores) / len(scores), 4)


def score_semantic_similarity_accuracy(
    results: list[dict[str, Any]],
    *,
    threshold: float = _GROUNDING_THRESHOLD,
) -> float:
    """Fraction of results whose similarity score meets the grounding threshold."""
    if not results:
        return 0.0
    above = sum(
        1 for r in results
        if float(
            (r.get("provenance") or {}).get("similarity_score")
            or r.get("match_score")
            or 0.0
        ) >= threshold
    )
    return round(above / len(results), 4)


def score_retrieval_quality(
    results: list[dict[str, Any]],
    *,
    relevant_ids: set[str] | None = None,
) -> dict[str, float]:
    """
    Compute all four retrieval quality dimensions in one call.

    Args:
        results: Retrieved result dicts with 'incident_id' and 'provenance'.
        relevant_ids: Ground truth set of incident IDs that should be retrieved.
                      If None, precision and recall are omitted.

    Returns:
        Dict with keys: retrieval_grounding_score, semantic_similarity_accuracy,
        and optionally retrieval_precision, retrieval_recall.
    """
    retrieved_ids = [r.get("incident_id", "") for r in results]
    metrics: dict[str, float] = {
        "retrieval_grounding_score": score_retrieval_grounding(results),
        "semantic_similarity_accuracy": score_semantic_similarity_accuracy(results),
    }
    if relevant_ids is not None:
        metrics["retrieval_precision"] = score_retrieval_precision(retrieved_ids, relevant_ids)
        metrics["retrieval_recall"] = score_retrieval_recall(retrieved_ids, relevant_ids)
    return metrics
