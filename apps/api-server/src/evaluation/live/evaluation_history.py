"""
Evaluation run history for SentinelOps Phase 47.

Persists evaluation run summaries in-process and supports
comparison across runs to detect regressions and improvements.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class EvaluationRunSummary:
    """Summary of one completed evaluation run."""

    run_id: str
    dataset_id: str
    dataset_version: str
    executed_at: str
    num_samples: int
    overall_accuracy: float
    mean_confidence: float
    calibration_error: float
    trend: str
    drift_detected: bool
    drift_direction: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def quality_score(self) -> float:
        """Composite quality: accuracy weighted by calibration penalty."""
        cal_penalty = min(0.30, self.calibration_error * 0.5)
        return max(0.0, self.overall_accuracy - cal_penalty)


@dataclass
class RunComparison:
    """Comparison between two evaluation runs."""

    baseline_run_id: str
    candidate_run_id: str
    accuracy_delta: float
    calibration_delta: float
    quality_delta: float
    regression_detected: bool
    improvement_detected: bool
    verdict: str  # "regression", "improvement", "neutral"

    _REGRESSION_THRESHOLD: float = 0.03

    def summary(self) -> str:
        return (
            f"{self.verdict}: acc={self.accuracy_delta:+.3f} "
            f"cal={self.calibration_delta:+.3f} "
            f"quality={self.quality_delta:+.3f}"
        )


class EvaluationHistory:
    """
    In-process store of evaluation run summaries.

    Supports regression detection between consecutive runs
    and retrieving the best/worst historical runs.
    """

    def __init__(self) -> None:
        self._runs: list[EvaluationRunSummary] = []

    def record(self, summary: EvaluationRunSummary) -> None:
        self._runs.append(summary)

    def record_from_report(
        self,
        run_id: str,
        dataset_id: str,
        dataset_version: str,
        report: Any,
    ) -> EvaluationRunSummary:
        """Build and record a summary from a LongitudinalReport."""
        drift_detected = False
        drift_direction = "stable"
        if report.drift is not None:
            drift_detected = report.drift.drift_detected
            drift_direction = report.drift.drift_direction

        mean_conf = 0.0
        if report.total_records > 0 and report.windows:
            mean_conf = sum(w.mean_confidence for w in report.windows) / len(report.windows)

        summary = EvaluationRunSummary(
            run_id=run_id,
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            executed_at=datetime.now(timezone.utc).isoformat(),
            num_samples=report.total_records,
            overall_accuracy=report.overall_accuracy,
            mean_confidence=mean_conf,
            calibration_error=report.overall_calibration_error,
            trend=report.trend,
            drift_detected=drift_detected,
            drift_direction=drift_direction,
        )
        self.record(summary)
        return summary

    def compare(self, baseline_id: str, candidate_id: str) -> RunComparison | None:
        """Compare two runs by their run_id. Returns None if either is missing."""
        baseline = self._find(baseline_id)
        candidate = self._find(candidate_id)
        if baseline is None or candidate is None:
            return None

        acc_delta = candidate.overall_accuracy - baseline.overall_accuracy
        cal_delta = candidate.calibration_error - baseline.calibration_error
        quality_delta = candidate.quality_score - baseline.quality_score

        threshold = RunComparison._REGRESSION_THRESHOLD
        regression = acc_delta < -threshold
        improvement = acc_delta > threshold

        if regression:
            verdict = "regression"
        elif improvement:
            verdict = "improvement"
        else:
            verdict = "neutral"

        return RunComparison(
            baseline_run_id=baseline_id,
            candidate_run_id=candidate_id,
            accuracy_delta=acc_delta,
            calibration_delta=cal_delta,
            quality_delta=quality_delta,
            regression_detected=regression,
            improvement_detected=improvement,
            verdict=verdict,
        )

    def compare_last_two(self) -> RunComparison | None:
        """Compare the two most recent runs, if at least two exist."""
        if len(self._runs) < 2:
            return None
        return self.compare(self._runs[-2].run_id, self._runs[-1].run_id)

    def best_run(self) -> EvaluationRunSummary | None:
        if not self._runs:
            return None
        return max(self._runs, key=lambda r: r.quality_score)

    def worst_run(self) -> EvaluationRunSummary | None:
        if not self._runs:
            return None
        return min(self._runs, key=lambda r: r.quality_score)

    def all_runs(self) -> list[EvaluationRunSummary]:
        return list(self._runs)

    def run_count(self) -> int:
        return len(self._runs)

    def clear(self) -> None:
        self._runs.clear()

    def _find(self, run_id: str) -> EvaluationRunSummary | None:
        for r in self._runs:
            if r.run_id == run_id:
                return r
        return None
