"""
Confidence calibration scoring for AI decisions.

Implements Expected Calibration Error (ECE), Brier score, reliability diagram
data, overconfidence/underconfidence detection.

A well-calibrated model: when it says confidence=0.8, it should be correct 80% of time.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agents.uncertainty import apply_temperature_scaling


@dataclass
class CalibrationBin:
    confidence_low: float
    confidence_high: float
    count: int
    correct: int

    @property
    def accuracy(self) -> float:
        return self.correct / self.count if self.count > 0 else 0.0

    @property
    def avg_confidence(self) -> float:
        return (self.confidence_low + self.confidence_high) / 2

    @property
    def calibration_gap(self) -> float:
        return abs(self.avg_confidence - self.accuracy)

    @property
    def is_overconfident(self) -> bool:
        return self.avg_confidence > self.accuracy + 0.05

    @property
    def is_underconfident(self) -> bool:
        return self.avg_confidence < self.accuracy - 0.05


@dataclass
class CalibrationReport:
    expected_calibration_error: float
    brier_score: float
    overconfidence_rate: float
    underconfidence_rate: float
    mean_confidence: float
    mean_accuracy: float
    confidence_accuracy_gap: float
    bins: list[CalibrationBin]
    abstain_recommendation_threshold: float
    low_confidence_escalation_threshold: float
    temperature: float = 1.0
    drift_detected: bool = False

    @property
    def is_well_calibrated(self) -> bool:
        return self.expected_calibration_error < 0.10

    @property
    def calibration_grade(self) -> str:
        ece = self.expected_calibration_error
        if ece < 0.05:
            return "EXCELLENT"
        if ece < 0.10:
            return "GOOD"
        if ece < 0.15:
            return "FAIR"
        if ece < 0.25:
            return "POOR"
        return "FAILING"

    def to_dict(self) -> dict[str, Any]:
        return {
            "expected_calibration_error": round(self.expected_calibration_error, 4),
            "brier_score": round(self.brier_score, 4),
            "overconfidence_rate": round(self.overconfidence_rate, 4),
            "underconfidence_rate": round(self.underconfidence_rate, 4),
            "mean_confidence": round(self.mean_confidence, 4),
            "mean_accuracy": round(self.mean_accuracy, 4),
            "confidence_accuracy_gap": round(self.confidence_accuracy_gap, 4),
            "calibration_grade": self.calibration_grade,
            "is_well_calibrated": self.is_well_calibrated,
            "abstain_threshold": self.abstain_recommendation_threshold,
            "escalation_threshold": self.low_confidence_escalation_threshold,
            "temperature": round(self.temperature, 4),
            "drift_detected": self.drift_detected,
        }


def build_reliability_curve(bins: list[CalibrationBin]) -> list[dict[str, float]]:
    return [
        {
            "confidence": round(bin_item.avg_confidence, 4),
            "accuracy": round(bin_item.accuracy, 4),
            "gap": round(bin_item.calibration_gap, 4),
        }
        for bin_item in bins
        if bin_item.count > 0
    ]


def compute_ece(
    confidences: list[float],
    correctness: list[bool],
    n_bins: int = 10,
) -> tuple[float, list[CalibrationBin]]:
    """Compute ECE and return calibration bins."""
    bins: list[CalibrationBin] = []
    n = len(confidences)
    if n == 0:
        return 0.0, bins

    bin_size = 1.0 / n_bins
    for i in range(n_bins):
        low = i * bin_size
        high = (i + 1) * bin_size
        in_bin = [
            (c, ok)
            for c, ok in zip(confidences, correctness, strict=False)
            if low <= c < high or (i == n_bins - 1 and c == 1.0)
        ]
        count = len(in_bin)
        correct = sum(1 for _, ok in in_bin if ok)
        bins.append(
            CalibrationBin(
                confidence_low=low,
                confidence_high=high,
                count=count,
                correct=correct,
            )
        )

    ece = sum((b.count / n) * b.calibration_gap for b in bins if b.count > 0)
    return ece, bins


def compute_brier_score(confidences: list[float], correctness: list[bool]) -> float:
    if not confidences:
        return 0.0
    return sum(
        (c - (1.0 if ok else 0.0)) ** 2 for c, ok in zip(confidences, correctness, strict=False)
    ) / len(confidences)


def find_abstain_threshold(
    confidences: list[float],
    correctness: list[bool],
    target_accuracy: float = 0.90,
) -> float:
    """Find the minimum confidence threshold where accuracy >= target_accuracy."""
    thresholds = sorted(set(confidences))
    for threshold in reversed(thresholds):
        above = [(c, ok) for c, ok in zip(confidences, correctness, strict=False) if c >= threshold]
        if not above:
            continue
        acc = sum(1 for _, ok in above if ok) / len(above)
        if acc >= target_accuracy:
            return threshold
    return 1.0


def fit_temperature_scale(confidences: list[float], correctness: list[bool]) -> float:
    """Find a simple temperature that minimizes Brier score on a fixed grid."""
    if not confidences:
        return 1.0
    best_temperature = 1.0
    best_score = float("inf")
    for step in range(5, 26):
        temperature = step / 10
        scaled = [apply_temperature_scaling(confidence, temperature) for confidence in confidences]
        score = compute_brier_score(scaled, correctness)
        if score < best_score:
            best_score = score
            best_temperature = temperature
    return round(best_temperature, 4)


def detect_confidence_drift(
    baseline_ece: float,
    current_ece: float,
    *,
    tolerance: float = 0.03,
) -> bool:
    return (current_ece - baseline_ece) > tolerance


def score_confidence_calibration(
    confidences: list[float],
    correctness: list[bool],
    *,
    baseline_ece: float = 0.0,
) -> CalibrationReport:
    n = len(confidences)
    if n == 0:
        return CalibrationReport(
            expected_calibration_error=0.0,
            brier_score=0.0,
            overconfidence_rate=0.0,
            underconfidence_rate=0.0,
            mean_confidence=0.0,
            mean_accuracy=0.0,
            confidence_accuracy_gap=0.0,
            bins=[],
            abstain_recommendation_threshold=0.85,
            low_confidence_escalation_threshold=0.55,
            temperature=1.0,
            drift_detected=False,
        )

    temperature = fit_temperature_scale(confidences, correctness)
    calibrated_confidences = [
        apply_temperature_scaling(confidence, temperature) for confidence in confidences
    ]
    ece, bins = compute_ece(calibrated_confidences, correctness)
    brier = compute_brier_score(calibrated_confidences, correctness)
    mean_conf = sum(confidences) / n
    mean_acc = sum(1 for ok in correctness if ok) / n

    overconfident_count = sum(1 for b in bins if b.count > 0 and b.is_overconfident)
    underconfident_count = sum(1 for b in bins if b.count > 0 and b.is_underconfident)
    non_empty = max(1, sum(1 for b in bins if b.count > 0))
    overconf_rate = overconfident_count / non_empty
    underconf_rate = underconfident_count / non_empty

    abstain_threshold = find_abstain_threshold(
        calibrated_confidences,
        correctness,
        target_accuracy=0.90,
    )
    escalation_threshold = find_abstain_threshold(
        calibrated_confidences,
        correctness,
        target_accuracy=0.75,
    )

    return CalibrationReport(
        expected_calibration_error=ece,
        brier_score=brier,
        overconfidence_rate=overconf_rate,
        underconfidence_rate=underconf_rate,
        mean_confidence=mean_conf,
        mean_accuracy=mean_acc,
        confidence_accuracy_gap=abs(mean_conf - mean_acc),
        bins=bins,
        abstain_recommendation_threshold=abstain_threshold,
        low_confidence_escalation_threshold=escalation_threshold,
        temperature=temperature,
        drift_detected=detect_confidence_drift(baseline_ece, ece),
    )


def build_calibration_data_from_benchmark(incidents: list) -> tuple[list[float], list[bool]]:
    """Extract (confidence, is_correct) pairs from benchmark incidents."""
    confidences = []
    correctness = []
    for inc in incidents:
        router = inc.mocked_tool_responses.get("router", {})
        predicted = router.get("incident_type", "unknown")
        confidence = router.get("confidence", 0.5)
        is_correct = predicted.strip().lower() == inc.golden_classification.strip().lower()
        confidences.append(confidence)
        correctness.append(is_correct)
    return confidences, correctness
