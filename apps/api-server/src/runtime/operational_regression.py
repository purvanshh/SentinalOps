"""
Operational regression detector for SentinelOps Phase 47.

Detects performance regressions between evaluation runs by comparing
key metrics: accuracy, calibration error, and severity-weighted accuracy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class MetricSnapshot:
    """Point-in-time metrics snapshot for regression comparison."""

    run_id: str
    accuracy: float
    calibration_error: float
    severity_weighted_accuracy: float
    completeness_weighted_accuracy: float
    trend: str
    window_count: int
    metadata: dict[str, Any] | None = None


@dataclass
class RegressionResult:
    """Result of comparing two metric snapshots."""

    baseline_run_id: str
    candidate_run_id: str
    accuracy_regressed: bool
    calibration_worsened: bool
    weighted_accuracy_regressed: bool
    overall_regression: bool
    accuracy_delta: float
    calibration_delta: float
    weighted_delta: float
    regression_score: float  # 0.0 = no regression, 1.0 = all metrics regressed
    verdict: str  # "pass", "warn", "fail"

    def summary(self) -> str:
        return (
            f"verdict={self.verdict} "
            f"acc={self.accuracy_delta:+.3f} "
            f"cal={self.calibration_delta:+.3f} "
            f"score={self.regression_score:.2f}"
        )


class OperationalRegressionDetector:
    """
    Compares two metric snapshots and classifies the result as pass/warn/fail.

    Thresholds:
      - accuracy regression: delta < -0.03
      - calibration worsened: calibration_error delta > +0.05
      - severity-weighted regression: delta < -0.03
      - verdict "warn": 1 metric regressed
      - verdict "fail": 2+ metrics regressed
    """

    _ACCURACY_THRESHOLD: float = -0.03
    _CALIBRATION_THRESHOLD: float = 0.05
    _WEIGHTED_THRESHOLD: float = -0.03

    def compare(self, baseline: MetricSnapshot, candidate: MetricSnapshot) -> RegressionResult:
        acc_delta = candidate.accuracy - baseline.accuracy
        cal_delta = candidate.calibration_error - baseline.calibration_error
        weighted_delta = candidate.severity_weighted_accuracy - baseline.severity_weighted_accuracy

        acc_reg = acc_delta < self._ACCURACY_THRESHOLD
        cal_worse = cal_delta > self._CALIBRATION_THRESHOLD
        weighted_reg = weighted_delta < self._WEIGHTED_THRESHOLD

        regressions = sum([acc_reg, cal_worse, weighted_reg])
        regression_score = regressions / 3.0
        overall = regressions >= 1

        if regressions >= 2:
            verdict = "fail"
        elif regressions == 1:
            verdict = "warn"
        else:
            verdict = "pass"

        return RegressionResult(
            baseline_run_id=baseline.run_id,
            candidate_run_id=candidate.run_id,
            accuracy_regressed=acc_reg,
            calibration_worsened=cal_worse,
            weighted_accuracy_regressed=weighted_reg,
            overall_regression=overall,
            accuracy_delta=acc_delta,
            calibration_delta=cal_delta,
            weighted_delta=weighted_delta,
            regression_score=regression_score,
            verdict=verdict,
        )

    def from_reports(
        self,
        baseline_run_id: str,
        baseline_report: Any,
        candidate_run_id: str,
        candidate_report: Any,
    ) -> RegressionResult:
        """Build snapshots directly from LongitudinalReport objects."""

        def _mean_sev_weighted(report: Any) -> float:
            if not report.windows:
                return 0.0
            return sum(w.severity_weighted_accuracy for w in report.windows) / len(report.windows)

        def _mean_comp_weighted(report: Any) -> float:
            if not report.windows:
                return 0.0
            return sum(w.completeness_weighted_accuracy for w in report.windows) / len(
                report.windows
            )

        base = MetricSnapshot(
            run_id=baseline_run_id,
            accuracy=baseline_report.overall_accuracy,
            calibration_error=baseline_report.overall_calibration_error,
            severity_weighted_accuracy=_mean_sev_weighted(baseline_report),
            completeness_weighted_accuracy=_mean_comp_weighted(baseline_report),
            trend=baseline_report.trend,
            window_count=baseline_report.num_windows,
        )
        cand = MetricSnapshot(
            run_id=candidate_run_id,
            accuracy=candidate_report.overall_accuracy,
            calibration_error=candidate_report.overall_calibration_error,
            severity_weighted_accuracy=_mean_sev_weighted(candidate_report),
            completeness_weighted_accuracy=_mean_comp_weighted(candidate_report),
            trend=candidate_report.trend,
            window_count=candidate_report.num_windows,
        )
        return self.compare(base, cand)
