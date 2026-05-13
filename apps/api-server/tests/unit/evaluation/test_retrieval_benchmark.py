"""
Phase 42 retrieval benchmark and quality scorer tests.

Proves:
  - score_retrieval_precision correctly measures relevant fraction.
  - score_retrieval_recall correctly measures coverage fraction.
  - score_retrieval_grounding returns mean similarity across results.
  - score_semantic_similarity_accuracy measures above-threshold fraction.
  - score_retrieval_quality bundles all four metrics.
  - run_retrieval_benchmark aggregates across cases and computes F1.
  - RetrievalBenchmarkReport.passes_quality_bar reflects thresholds.
"""
from __future__ import annotations

import pytest

from evaluation.retrieval_benchmark import (
    RetrievalBenchmarkCase,
    RetrievalBenchmarkReport,
    run_retrieval_benchmark,
)
from evaluation.scorers.retrieval_quality_scorer import (
    score_retrieval_grounding,
    score_retrieval_precision,
    score_retrieval_recall,
    score_retrieval_quality,
    score_semantic_similarity_accuracy,
)


def _make_result(incident_id: str, score: float) -> dict:
    return {
        "incident_id": incident_id,
        "match_score": score,
        "provenance": {"similarity_score": score},
    }


# ─── score_retrieval_precision ────────────────────────────────────────────────


def test_precision_all_relevant() -> None:
    retrieved = ["INC-001", "INC-002"]
    relevant = {"INC-001", "INC-002"}
    assert score_retrieval_precision(retrieved, relevant) == pytest.approx(1.0)


def test_precision_none_relevant() -> None:
    retrieved = ["INC-001", "INC-002"]
    relevant = {"INC-999"}
    assert score_retrieval_precision(retrieved, relevant) == pytest.approx(0.0)


def test_precision_partial() -> None:
    retrieved = ["INC-001", "INC-002", "INC-003"]
    relevant = {"INC-001", "INC-003"}
    assert score_retrieval_precision(retrieved, relevant) == pytest.approx(2 / 3, abs=0.01)


def test_precision_empty_retrieved_returns_zero() -> None:
    assert score_retrieval_precision([], {"INC-001"}) == pytest.approx(0.0)


# ─── score_retrieval_recall ───────────────────────────────────────────────────


def test_recall_all_found() -> None:
    retrieved = ["INC-001", "INC-002"]
    relevant = {"INC-001", "INC-002"}
    assert score_retrieval_recall(retrieved, relevant) == pytest.approx(1.0)


def test_recall_none_found() -> None:
    retrieved = ["INC-999"]
    relevant = {"INC-001", "INC-002"}
    assert score_retrieval_recall(retrieved, relevant) == pytest.approx(0.0)


def test_recall_partial() -> None:
    retrieved = ["INC-001"]
    relevant = {"INC-001", "INC-002"}
    assert score_retrieval_recall(retrieved, relevant) == pytest.approx(0.5, abs=0.01)


def test_recall_empty_relevant_returns_one() -> None:
    assert score_retrieval_recall(["INC-001"], set()) == pytest.approx(1.0)


# ─── score_retrieval_grounding ────────────────────────────────────────────────


def test_grounding_score_is_mean_of_similarities() -> None:
    results = [_make_result("INC-001", 0.80), _make_result("INC-002", 0.60)]
    assert score_retrieval_grounding(results) == pytest.approx(0.70, abs=0.01)


def test_grounding_score_empty_returns_zero() -> None:
    assert score_retrieval_grounding([]) == pytest.approx(0.0)


# ─── score_semantic_similarity_accuracy ───────────────────────────────────────


def test_similarity_accuracy_all_above_threshold() -> None:
    results = [_make_result("INC-001", 0.80), _make_result("INC-002", 0.75)]
    assert score_semantic_similarity_accuracy(results) == pytest.approx(1.0)


def test_similarity_accuracy_none_above_threshold() -> None:
    results = [_make_result("INC-001", 0.50), _make_result("INC-002", 0.40)]
    assert score_semantic_similarity_accuracy(results) == pytest.approx(0.0)


def test_similarity_accuracy_empty_returns_zero() -> None:
    assert score_semantic_similarity_accuracy([]) == pytest.approx(0.0)


# ─── score_retrieval_quality ──────────────────────────────────────────────────


def test_score_retrieval_quality_includes_all_four_dimensions() -> None:
    results = [_make_result("INC-001", 0.85)]
    metrics = score_retrieval_quality(results, relevant_ids={"INC-001"})
    assert "retrieval_precision" in metrics
    assert "retrieval_recall" in metrics
    assert "retrieval_grounding_score" in metrics
    assert "semantic_similarity_accuracy" in metrics


def test_score_retrieval_quality_without_relevant_ids_omits_precision_recall() -> None:
    results = [_make_result("INC-001", 0.85)]
    metrics = score_retrieval_quality(results)
    assert "retrieval_grounding_score" in metrics
    assert "semantic_similarity_accuracy" in metrics
    assert "retrieval_precision" not in metrics
    assert "retrieval_recall" not in metrics


# ─── run_retrieval_benchmark ──────────────────────────────────────────────────


def test_benchmark_empty_cases_returns_zero_report() -> None:
    report = run_retrieval_benchmark([])
    assert report.total_cases == 0
    assert report.overall_retrieval_quality == 0.0


def test_benchmark_perfect_retrieval_scores_one() -> None:
    case = RetrievalBenchmarkCase(
        query="database latency spike",
        relevant_incident_ids={"INC-001"},
        simulated_results=[_make_result("INC-001", 0.90)],
    )
    report = run_retrieval_benchmark([case])
    assert report.mean_precision == pytest.approx(1.0)
    assert report.mean_recall == pytest.approx(1.0)
    assert report.overall_retrieval_quality == pytest.approx(1.0)


def test_benchmark_aggregates_multiple_cases() -> None:
    cases = [
        RetrievalBenchmarkCase(
            query="database timeout",
            relevant_incident_ids={"INC-001"},
            simulated_results=[_make_result("INC-001", 0.85)],
        ),
        RetrievalBenchmarkCase(
            query="payment api degradation",
            relevant_incident_ids={"INC-002"},
            simulated_results=[_make_result("INC-002", 0.75), _make_result("INC-003", 0.65)],
        ),
    ]
    report = run_retrieval_benchmark(cases)
    assert report.total_cases == 2
    assert len(report.per_case_metrics) == 2


def test_benchmark_suppresses_low_score_results() -> None:
    case = RetrievalBenchmarkCase(
        query="latency spike",
        relevant_incident_ids={"INC-001"},
        simulated_results=[
            _make_result("INC-001", 0.90),
            _make_result("INC-BAD", 0.15),
        ],
    )
    report = run_retrieval_benchmark([case])
    assert report.suppressed_count >= 1


def test_benchmark_passes_quality_bar_when_metrics_are_high() -> None:
    cases = [
        RetrievalBenchmarkCase(
            query="database connection pool exhausted",
            relevant_incident_ids={"INC-001"},
            simulated_results=[_make_result("INC-001", 0.88)],
        ),
    ]
    report = run_retrieval_benchmark(cases)
    assert report.passes_quality_bar is True


def test_benchmark_fails_quality_bar_when_low_grounding() -> None:
    cases = [
        RetrievalBenchmarkCase(
            query="unrelated query",
            relevant_incident_ids={"INC-001"},
            simulated_results=[_make_result("INC-WRONG", 0.30)],
        ),
    ]
    report = run_retrieval_benchmark(cases)
    assert report.passes_quality_bar is False
