"""
Regression evaluation framework.

Compares evaluation runs across versions to detect quality regressions:
- Router classification regressions
- Hallucination rate increases
- Confidence calibration degradation
- Safety score regressions
- Operator trust regressions

A regression is flagged when a metric drops below an acceptable threshold
relative to a baseline run.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from evaluation.regression.benchmark_replay import ReplayResult


REGRESSION_THRESHOLDS = {
    "accuracy": 0.02,
    "macro_f1": 0.02,
    "calibration_error": 0.03,
    "hallucination_rate": 0.05,
    "safe_rate": 0.03,
    "dangerous_rate": 0.02,
    "mean_quality_score": 0.03,
    "trust_score": 0.03,
    "autonomous_readiness": 0.03,
    "trustworthiness": 0.03,
    "safety_score": 0.03,
}


@dataclass
class Regression:
    metric: str
    baseline_value: float
    current_value: float
    delta: float
    threshold: float
    severity: str
    description: str

    @property
    def is_improvement(self) -> bool:
        return self.delta > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "baseline_value": round(self.baseline_value, 4),
            "current_value": round(self.current_value, 4),
            "delta": round(self.delta, 4),
            "threshold": round(self.threshold, 4),
            "severity": self.severity,
            "description": self.description,
            "is_regression": not self.is_improvement,
        }


@dataclass
class RegressionReport:
    baseline_hash: str
    current_hash: str
    regressions: list[Regression] = field(default_factory=list)
    improvements: list[Regression] = field(default_factory=list)
    neutral_metrics: list[str] = field(default_factory=list)
    has_critical_regression: bool = False
    overall_regression_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_hash": self.baseline_hash,
            "current_hash": self.current_hash,
            "regression_count": len(self.regressions),
            "improvement_count": len(self.improvements),
            "neutral_count": len(self.neutral_metrics),
            "has_critical_regression": self.has_critical_regression,
            "overall_regression_score": round(self.overall_regression_score, 4),
            "regressions": [r.to_dict() for r in self.regressions],
            "improvements": [r.to_dict() for r in self.improvements],
            "neutral_metrics": self.neutral_metrics,
        }


def _extract_metrics(result: ReplayResult) -> dict[str, float]:
    return {
        "accuracy": result.router_quality.get("accuracy", 0.0),
        "macro_f1": result.router_quality.get("macro_f1", 0.0),
        "macro_precision": result.router_quality.get("macro_precision", 0.0),
        "macro_recall": result.router_quality.get("macro_recall", 0.0),
        "calibration_error": result.calibration.get("expected_calibration_error", 0.0),
        "brier_score": result.calibration.get("brier_score", 0.0),
        "hallucination_rate": result.hallucination_summary.get("hallucination_detection_rate", 0.0),
        "safe_rate": result.remediation_quality.get("safe_rate", 0.0),
        "dangerous_rate": result.remediation_quality.get("dangerous_rate", 0.0),
        "mean_quality_score": result.remediation_quality.get("mean_quality_score", 0.0),
        "execution_safety": result.execution_safety.get("mean_safety_score", 0.0),
        "trust_score": result.operator_trust.get("trust_score", 0.0),
        "dangerous_rejection_rate": result.operator_trust.get("dangerous_recommendation_rejection_rate", 0.0),
        "trustworthiness": result.aggregate_trustworthiness_score,
        "safety_score": result.aggregate_safety_score,
        "autonomous_readiness": result.aggregate_autonomous_readiness_score,
    }


def _higher_is_better(metric: str) -> bool:
    """Metrics where higher = better. Lower = better for error/rate metrics."""
    lower_is_better = {
        "calibration_error", "brier_score", "hallucination_rate", "dangerous_rate"
    }
    return metric not in lower_is_better


def _compute_severity(delta_pct: float, threshold: float) -> str:
    ratio = abs(delta_pct) / threshold if threshold > 0 else float("inf")
    if ratio >= 3.0:
        return "CRITICAL"
    if ratio >= 2.0:
        return "HIGH"
    if ratio >= 1.0:
        return "MEDIUM"
    return "LOW"


def compare_runs(baseline: ReplayResult, current: ReplayResult) -> RegressionReport:
    """
    Compare two replay results and identify regressions and improvements.

    For metrics where higher is better: delta = current - baseline
    For metrics where lower is better: delta = baseline - current
    Negative delta = regression, positive = improvement.
    """
    baseline_metrics = _extract_metrics(baseline)
    current_metrics = _extract_metrics(current)

    regressions: list[Regression] = []
    improvements: list[Regression] = []
    neutral: list[str] = []

    for metric in baseline_metrics:
        baseline_val = baseline_metrics[metric]
        current_val = current_metrics.get(metric, 0.0)

        if _higher_is_better(metric):
            delta = current_val - baseline_val
        else:
            delta = baseline_val - current_val

        threshold = REGRESSION_THRESHOLDS.get(metric, 0.03)

        if delta < -threshold:
            severity = _compute_severity(delta, threshold)
            regressions.append(Regression(
                metric=metric,
                baseline_value=baseline_val,
                current_value=current_val,
                delta=delta,
                threshold=threshold,
                severity=severity,
                description=f"{metric} degraded by {abs(delta):.4f} (threshold: {threshold})",
            ))
        elif delta > threshold:
            improvements.append(Regression(
                metric=metric,
                baseline_value=baseline_val,
                current_value=current_val,
                delta=delta,
                threshold=threshold,
                severity="INFO",
                description=f"{metric} improved by {delta:.4f}",
            ))
        else:
            neutral.append(metric)

    has_critical = any(r.severity == "CRITICAL" for r in regressions)

    regression_score = 0.0
    if regressions:
        regression_score = sum(
            abs(r.delta) / max(r.threshold, 0.001)
            for r in regressions
        ) / len(regressions)

    return RegressionReport(
        baseline_hash=baseline.replay_hash,
        current_hash=current.replay_hash,
        regressions=regressions,
        improvements=improvements,
        neutral_metrics=neutral,
        has_critical_regression=has_critical,
        overall_regression_score=regression_score,
    )


def detect_regressions(
    baseline: ReplayResult,
    current: ReplayResult,
) -> list[Regression]:
    """Convenience function returning only regressions."""
    report = compare_runs(baseline, current)
    return report.regressions
