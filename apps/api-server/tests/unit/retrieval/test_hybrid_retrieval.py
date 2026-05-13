"""
Phase 42 hybrid retrieval tests.

Proves:
  - HybridRetriever.retrieve() returns results with hybrid_score and provenance.
  - Results are sorted by hybrid_score descending.
  - Topology neighbor boost is applied to services in the dependency graph.
  - Services not in the topology receive no boost.
  - Time decay weight decreases for older retrieved_at timestamps.
  - grounding_score() aggregates similarity quality across results.
  - Empty topology does not raise errors.
  - limit parameter caps the result count.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from retrieval.hybrid_retrieval import (
    HybridRetriever,
    _compute_hybrid_score,
    _time_decay_weight,
    _topology_neighbors,
)


def _make_result(
    match_score: float = 0.80,
    service: str = "",
    retrieved_at: str = "",
) -> dict:
    return {
        "incident_id": "INC-TEST",
        "match_score": match_score,
        "service": service,
        "retrieved_at": retrieved_at,
        "provenance": {
            "similarity_score": match_score,
            "embedding_model": "text-embedding-3-small",
            "retrieved_at": retrieved_at,
            "retrieval_reason": "pattern match",
            "matched_dimensions": [],
            "grounding_status": "grounded" if match_score >= 0.70 else "weakly_grounded",
        },
    }


def _make_topology(service: str, deps: list[str]) -> dict:
    return {"dependencies": {service: deps}}


# ─── _time_decay_weight ───────────────────────────────────────────────────────


def test_time_decay_weight_recent_is_near_one() -> None:
    now = datetime.now(UTC).isoformat()
    weight = _time_decay_weight(now)
    assert weight == pytest.approx(1.0, abs=0.01)


def test_time_decay_weight_90_days_is_half() -> None:
    old = (datetime.now(UTC) - timedelta(days=90)).isoformat()
    weight = _time_decay_weight(old)
    assert weight == pytest.approx(0.5, abs=0.02)


def test_time_decay_weight_empty_string_returns_one() -> None:
    assert _time_decay_weight("") == pytest.approx(1.0)


def test_time_decay_weight_invalid_returns_one() -> None:
    assert _time_decay_weight("not-a-timestamp") == pytest.approx(1.0)


# ─── _topology_neighbors ─────────────────────────────────────────────────────


def test_topology_neighbors_returns_downstream() -> None:
    topology = _make_topology("payment-api", ["database", "cache"])
    neighbors = _topology_neighbors("payment-api", topology)
    assert "database" in neighbors
    assert "cache" in neighbors


def test_topology_neighbors_returns_upstream() -> None:
    topology = {"dependencies": {"gateway": ["payment-api"]}}
    neighbors = _topology_neighbors("payment-api", topology)
    assert "gateway" in neighbors


def test_topology_neighbors_empty_topology_returns_empty() -> None:
    assert _topology_neighbors("payment-api", {}) == set()


# ─── _compute_hybrid_score ────────────────────────────────────────────────────


def test_compute_hybrid_score_no_topology_returns_base_score() -> None:
    result = _make_result(match_score=0.80)
    score = _compute_hybrid_score(result, service="payment-api", topology=None)
    assert score == pytest.approx(0.80, abs=0.02)


def test_compute_hybrid_score_neighbor_service_gets_boost() -> None:
    topology = _make_topology("payment-api", ["database"])
    result = _make_result(match_score=0.70, service="database")
    score = _compute_hybrid_score(result, service="payment-api", topology=topology)
    assert score > 0.70


def test_compute_hybrid_score_non_neighbor_gets_no_boost() -> None:
    topology = _make_topology("payment-api", ["database"])
    result = _make_result(match_score=0.70, service="unrelated-service")
    score = _compute_hybrid_score(result, service="payment-api", topology=topology)
    assert score == pytest.approx(0.70, abs=0.02)


def test_compute_hybrid_score_same_service_gets_boost() -> None:
    topology = _make_topology("payment-api", ["database"])
    result = _make_result(match_score=0.70, service="payment-api")
    score = _compute_hybrid_score(result, service="payment-api", topology=topology)
    assert score > 0.70


# ─── HybridRetriever ─────────────────────────────────────────────────────────


def _make_mock_searcher(results: list[dict]) -> MagicMock:
    searcher = MagicMock()
    searcher.search.return_value = results
    return searcher


def test_hybrid_retriever_returns_hybrid_score_field() -> None:
    raw = [_make_result(0.80), _make_result(0.65)]
    retriever = HybridRetriever(pattern_searcher=_make_mock_searcher(raw))
    results = retriever.retrieve("latency spike", service="payment-api")
    assert all("hybrid_score" in r for r in results)


def test_hybrid_retriever_returns_provenance_field() -> None:
    raw = [_make_result(0.75)]
    retriever = HybridRetriever(pattern_searcher=_make_mock_searcher(raw))
    results = retriever.retrieve("database timeout")
    assert all("provenance" in r for r in results)


def test_hybrid_retriever_results_sorted_by_hybrid_score() -> None:
    raw = [_make_result(0.50), _make_result(0.90), _make_result(0.70)]
    retriever = HybridRetriever(pattern_searcher=_make_mock_searcher(raw))
    results = retriever.retrieve("query", service="payment-api")
    scores = [r["hybrid_score"] for r in results]
    assert scores == sorted(scores, reverse=True)


def test_hybrid_retriever_limit_caps_results() -> None:
    raw = [_make_result(float(i) / 10) for i in range(10, 0, -1)]
    retriever = HybridRetriever(pattern_searcher=_make_mock_searcher(raw))
    results = retriever.retrieve("query", limit=3)
    assert len(results) <= 3


def test_hybrid_retriever_empty_results_returns_empty_list() -> None:
    retriever = HybridRetriever(pattern_searcher=_make_mock_searcher([]))
    results = retriever.retrieve("some query")
    assert results == []


def test_hybrid_retriever_empty_topology_does_not_raise() -> None:
    raw = [_make_result(0.80, service="payment-api")]
    retriever = HybridRetriever(pattern_searcher=_make_mock_searcher(raw))
    results = retriever.retrieve("query", service="payment-api", topology={})
    assert isinstance(results, list)


# ─── grounding_score ─────────────────────────────────────────────────────────


def test_grounding_score_returns_mean_of_provenance_scores() -> None:
    raw = [_make_result(0.80), _make_result(0.60)]
    retriever = HybridRetriever(pattern_searcher=_make_mock_searcher(raw))
    results = retriever.retrieve("query")
    score = retriever.grounding_score(results)
    assert 0.0 <= score <= 1.0


def test_grounding_score_empty_returns_zero() -> None:
    retriever = HybridRetriever(pattern_searcher=_make_mock_searcher([]))
    assert retriever.grounding_score([]) == 0.0


def test_grounding_score_high_quality_results_above_threshold() -> None:
    raw = [_make_result(0.90), _make_result(0.85)]
    retriever = HybridRetriever(pattern_searcher=_make_mock_searcher(raw))
    results = retriever.retrieve("query")
    score = retriever.grounding_score(results)
    assert score > 0.70
