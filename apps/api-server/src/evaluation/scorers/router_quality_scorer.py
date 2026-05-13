"""
Router classification quality evaluation.

Measures: confusion matrix, precision, recall, F1, confidence calibration,
false positive rate, false negative rate.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class RouterPrediction:
    incident_id: str
    predicted_type: str
    actual_type: str
    confidence: float
    is_fallback: bool = False
    is_degraded_mode: bool = False


@dataclass
class ConfusionMatrix:
    labels: list[str]
    matrix: dict[str, dict[str, int]] = field(default_factory=dict)

    def add(self, actual: str, predicted: str) -> None:
        if actual not in self.matrix:
            self.matrix[actual] = defaultdict(int)
        self.matrix[actual][predicted] += 1

    def true_positives(self, label: str) -> int:
        return self.matrix.get(label, {}).get(label, 0)

    def false_positives(self, label: str) -> int:
        total = 0
        for actual, preds in self.matrix.items():
            if actual != label:
                total += preds.get(label, 0)
        return total

    def false_negatives(self, label: str) -> int:
        row = self.matrix.get(label, {})
        return sum(count for pred, count in row.items() if pred != label)

    def precision(self, label: str) -> float:
        tp = self.true_positives(label)
        fp = self.false_positives(label)
        return tp / (tp + fp) if (tp + fp) > 0 else 0.0

    def recall(self, label: str) -> float:
        tp = self.true_positives(label)
        fn = self.false_negatives(label)
        return tp / (tp + fn) if (tp + fn) > 0 else 0.0

    def f1(self, label: str) -> float:
        p = self.precision(label)
        r = self.recall(label)
        return 2 * p * r / (p + r) if (p + r) > 0 else 0.0

    def accuracy(self) -> float:
        correct = sum(self.matrix.get(label, {}).get(label, 0) for label in self.labels)
        total = sum(sum(preds.values()) for preds in self.matrix.values())
        return correct / total if total > 0 else 0.0

    def macro_precision(self) -> float:
        scores = [self.precision(label) for label in self.labels if self.matrix.get(label)]
        return sum(scores) / len(scores) if scores else 0.0

    def macro_recall(self) -> float:
        scores = [self.recall(label) for label in self.labels if self.matrix.get(label)]
        return sum(scores) / len(scores) if scores else 0.0

    def macro_f1(self) -> float:
        scores = [self.f1(label) for label in self.labels if self.matrix.get(label)]
        return sum(scores) / len(scores) if scores else 0.0


@dataclass
class RouterQualityReport:
    total_predictions: int
    accuracy: float
    macro_precision: float
    macro_recall: float
    macro_f1: float
    false_positive_rate: float
    false_negative_rate: float
    per_class_metrics: dict[str, dict[str, float]]
    fallback_accuracy: float
    degraded_mode_accuracy: float
    high_confidence_accuracy: float
    low_confidence_accuracy: float
    confidence_threshold_analysis: dict[str, float]

    def to_dict(self) -> dict:
        return {
            "total_predictions": self.total_predictions,
            "accuracy": round(self.accuracy, 4),
            "macro_precision": round(self.macro_precision, 4),
            "macro_recall": round(self.macro_recall, 4),
            "macro_f1": round(self.macro_f1, 4),
            "false_positive_rate": round(self.false_positive_rate, 4),
            "false_negative_rate": round(self.false_negative_rate, 4),
            "per_class_metrics": {
                k: {mk: round(mv, 4) for mk, mv in v.items()}
                for k, v in self.per_class_metrics.items()
            },
            "fallback_accuracy": round(self.fallback_accuracy, 4),
            "degraded_mode_accuracy": round(self.degraded_mode_accuracy, 4),
            "high_confidence_accuracy": round(self.high_confidence_accuracy, 4),
            "low_confidence_accuracy": round(self.low_confidence_accuracy, 4),
        }


def _subset_accuracy(predictions: list[RouterPrediction]) -> float:
    if not predictions:
        return -1.0
    correct = sum(1 for p in predictions if p.predicted_type == p.actual_type)
    return correct / len(predictions)


def score_router_quality(predictions: list[RouterPrediction]) -> RouterQualityReport:
    labels = sorted(set(p.actual_type for p in predictions))
    cm = ConfusionMatrix(labels=labels)
    for p in predictions:
        cm.add(p.actual_type, p.predicted_type)

    per_class: dict[str, dict[str, float]] = {}
    for label in labels:
        per_class[label] = {
            "precision": cm.precision(label),
            "recall": cm.recall(label),
            "f1": cm.f1(label),
            "true_positives": float(cm.true_positives(label)),
            "false_positives": float(cm.false_positives(label)),
            "false_negatives": float(cm.false_negatives(label)),
        }

    total_fp = sum(cm.false_positives(label) for label in labels)
    total_fn = sum(cm.false_negatives(label) for label in labels)
    total = len(predictions)
    fp_rate = total_fp / total if total > 0 else 0.0
    fn_rate = total_fn / total if total > 0 else 0.0

    fallback_preds = [p for p in predictions if p.is_fallback]
    degraded_preds = [p for p in predictions if p.is_degraded_mode]
    high_conf_preds = [p for p in predictions if p.confidence >= 0.75]
    low_conf_preds = [p for p in predictions if p.confidence < 0.60]

    thresholds = [0.5, 0.6, 0.7, 0.8, 0.9]
    threshold_analysis: dict[str, float] = {}
    for t in thresholds:
        above = [p for p in predictions if p.confidence >= t]
        threshold_analysis[f"accuracy_at_{t}"] = _subset_accuracy(above)

    return RouterQualityReport(
        total_predictions=total,
        accuracy=cm.accuracy(),
        macro_precision=cm.macro_precision(),
        macro_recall=cm.macro_recall(),
        macro_f1=cm.macro_f1(),
        false_positive_rate=fp_rate,
        false_negative_rate=fn_rate,
        per_class_metrics=per_class,
        fallback_accuracy=_subset_accuracy(fallback_preds),
        degraded_mode_accuracy=_subset_accuracy(degraded_preds),
        high_confidence_accuracy=_subset_accuracy(high_conf_preds),
        low_confidence_accuracy=_subset_accuracy(low_conf_preds),
        confidence_threshold_analysis=threshold_analysis,
    )


def build_predictions_from_benchmark(incidents: list) -> list[RouterPrediction]:
    """Build RouterPrediction list from benchmark incidents using mocked router responses."""
    predictions = []
    for inc in incidents:
        router = inc.mocked_tool_responses.get("router", {})
        predicted_type = router.get("incident_type", "unknown")
        confidence = router.get("confidence", 0.5)
        is_fallback = confidence < 0.55
        is_degraded = inc.requires_escalation and confidence < 0.55
        predictions.append(
            RouterPrediction(
                incident_id=inc.id,
                predicted_type=predicted_type,
                actual_type=inc.golden_classification,
                confidence=confidence,
                is_fallback=is_fallback,
                is_degraded_mode=is_degraded,
            )
        )
    return predictions
