"""
Semantic retrieval benchmark for SentinelOps Phase 42.

Runs a deterministic evaluation of retrieval quality across a fixture set of
query/relevant-incident pairs. Produces metrics:
  - retrieval_precision
  - retrieval_recall
  - retrieval_grounding_score
  - semantic_similarity_accuracy
  - overall_retrieval_quality (harmonic mean of precision and recall)

The benchmark is intentionally self-contained: it uses the ConsistencyChecker
and retrieval quality scorer without live Qdrant/embedding API calls, allowing
regression testing in CI environments.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any

from evaluation.scorers.retrieval_quality_scorer import score_retrieval_quality
from retrieval.consistency_checker import run_consistency_check


@dataclass
class RetrievalBenchmarkCase:
    """A single benchmark query with known relevant incident IDs."""

    query: str
    relevant_incident_ids: set[str]
    simulated_results: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class RetrievalBenchmarkReport:
    """Aggregated retrieval quality metrics across all benchmark cases."""

    total_cases: int
    mean_precision: float
    mean_recall: float
    mean_grounding_score: float
    mean_similarity_accuracy: float
    overall_retrieval_quality: float
    suppressed_count: int
    per_case_metrics: list[dict[str, Any]] = field(default_factory=list)

    @property
    def passes_quality_bar(self) -> bool:
        """True when grounding score is acceptable for production use."""
        return self.mean_grounding_score >= 0.60 and self.overall_retrieval_quality >= 0.50


def _harmonic_mean(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return round(2 * precision * recall / (precision + recall), 4)


def run_retrieval_benchmark(cases: list[RetrievalBenchmarkCase]) -> RetrievalBenchmarkReport:
    """
    Evaluate retrieval quality across a list of benchmark cases.

    Each case provides simulated_results (pre-fetched retrieval output) and
    the ground-truth set of relevant incident IDs.
    """
    if not cases:
        return RetrievalBenchmarkReport(
            total_cases=0,
            mean_precision=0.0,
            mean_recall=0.0,
            mean_grounding_score=0.0,
            mean_similarity_accuracy=0.0,
            overall_retrieval_quality=0.0,
            suppressed_count=0,
        )

    per_case: list[dict[str, Any]] = []
    total_suppressed = 0

    for case in cases:
        metrics = score_retrieval_quality(
            case.simulated_results,
            relevant_ids=case.relevant_incident_ids,
        )
        report = run_consistency_check([], case.simulated_results)
        total_suppressed += report.suppression_count

        per_case.append(
            {
                "query": case.query,
                "suppressed": report.suppression_count,
                **metrics,
            }
        )

    precisions = [c.get("retrieval_precision", 0.0) for c in per_case]
    recalls = [c.get("retrieval_recall", 0.0) for c in per_case]
    groundings = [c["retrieval_grounding_score"] for c in per_case]
    accuracies = [c["semantic_similarity_accuracy"] for c in per_case]

    mean_precision = round(statistics.mean(precisions), 4)
    mean_recall = round(statistics.mean(recalls), 4)

    return RetrievalBenchmarkReport(
        total_cases=len(cases),
        mean_precision=mean_precision,
        mean_recall=mean_recall,
        mean_grounding_score=round(statistics.mean(groundings), 4),
        mean_similarity_accuracy=round(statistics.mean(accuracies), 4),
        overall_retrieval_quality=_harmonic_mean(mean_precision, mean_recall),
        suppressed_count=total_suppressed,
        per_case_metrics=per_case,
    )
