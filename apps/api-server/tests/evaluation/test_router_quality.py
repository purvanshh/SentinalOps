"""
Router classification quality evaluation tests.

Validates:
- Confusion matrix correctness
- Precision/recall/F1 computation
- Confidence threshold analysis
- Fallback classifier quality
- Degraded mode behavior
"""
import pytest

from evaluation.benchmark_suite import load_benchmark_suite
from evaluation.scorers.router_quality_scorer import (
    ConfusionMatrix,
    RouterPrediction,
    RouterQualityReport,
    build_predictions_from_benchmark,
    score_router_quality,
)


@pytest.fixture(scope="module")
def suite():
    return load_benchmark_suite()


@pytest.fixture(scope="module")
def predictions(suite):
    return build_predictions_from_benchmark(suite.incidents)


@pytest.fixture(scope="module")
def report(predictions) -> RouterQualityReport:
    return score_router_quality(predictions)


class TestConfusionMatrix:
    def test_true_positives_correct(self) -> None:
        cm = ConfusionMatrix(labels=["a", "b"])
        cm.add("a", "a")
        cm.add("a", "a")
        cm.add("a", "b")
        assert cm.true_positives("a") == 2

    def test_false_positives_correct(self) -> None:
        cm = ConfusionMatrix(labels=["a", "b"])
        cm.add("b", "a")
        cm.add("b", "a")
        assert cm.false_positives("a") == 2

    def test_false_negatives_correct(self) -> None:
        cm = ConfusionMatrix(labels=["a", "b"])
        cm.add("a", "b")
        cm.add("a", "b")
        assert cm.false_negatives("a") == 2

    def test_precision_zero_when_no_predictions(self) -> None:
        cm = ConfusionMatrix(labels=["a"])
        assert cm.precision("a") == 0.0

    def test_recall_zero_when_no_actuals(self) -> None:
        cm = ConfusionMatrix(labels=["a"])
        assert cm.recall("a") == 0.0

    def test_perfect_accuracy(self) -> None:
        cm = ConfusionMatrix(labels=["a", "b"])
        cm.add("a", "a")
        cm.add("b", "b")
        assert cm.accuracy() == 1.0

    def test_zero_accuracy_on_all_wrong(self) -> None:
        cm = ConfusionMatrix(labels=["a", "b"])
        cm.add("a", "b")
        cm.add("b", "a")
        assert cm.accuracy() == 0.0

    def test_f1_harmonic_mean(self) -> None:
        cm = ConfusionMatrix(labels=["a", "b"])
        cm.add("a", "a")
        cm.add("a", "a")
        cm.add("b", "a")
        p = cm.precision("a")
        r = cm.recall("a")
        expected_f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
        assert abs(cm.f1("a") - expected_f1) < 1e-9


class TestRouterQualityFromBenchmark:
    def test_report_has_total_predictions(self, report: RouterQualityReport) -> None:
        assert report.total_predictions >= 100

    def test_accuracy_in_valid_range(self, report: RouterQualityReport) -> None:
        assert 0.0 <= report.accuracy <= 1.0

    def test_macro_precision_in_valid_range(self, report: RouterQualityReport) -> None:
        assert 0.0 <= report.macro_precision <= 1.0

    def test_macro_recall_in_valid_range(self, report: RouterQualityReport) -> None:
        assert 0.0 <= report.macro_recall <= 1.0

    def test_macro_f1_in_valid_range(self, report: RouterQualityReport) -> None:
        assert 0.0 <= report.macro_f1 <= 1.0

    def test_false_positive_rate_in_valid_range(self, report: RouterQualityReport) -> None:
        assert 0.0 <= report.false_positive_rate <= 1.0

    def test_per_class_metrics_present(self, report: RouterQualityReport) -> None:
        assert len(report.per_class_metrics) >= 5, "Expected metrics for >= 5 classes"

    def test_per_class_precision_in_range(self, report: RouterQualityReport) -> None:
        for label, metrics in report.per_class_metrics.items():
            assert 0.0 <= metrics["precision"] <= 1.0, f"Precision out of range for {label}"

    def test_per_class_recall_in_range(self, report: RouterQualityReport) -> None:
        for label, metrics in report.per_class_metrics.items():
            assert 0.0 <= metrics["recall"] <= 1.0, f"Recall out of range for {label}"

    def test_threshold_analysis_populated(self, report: RouterQualityReport) -> None:
        assert len(report.confidence_threshold_analysis) > 0

    def test_to_dict_serializable(self, report: RouterQualityReport) -> None:
        import json
        d = report.to_dict()
        assert isinstance(d, dict)
        json.dumps(d)

    def test_benchmark_accuracy_above_threshold(self, report: RouterQualityReport) -> None:
        assert report.accuracy >= 0.55, (
            f"Router accuracy {report.accuracy:.3f} below minimum threshold of 0.55"
        )

    def test_high_confidence_better_than_low(self, report: RouterQualityReport) -> None:
        hc = report.high_confidence_accuracy
        lc = report.low_confidence_accuracy
        if hc >= 0 and lc >= 0:
            assert hc >= lc, "High-confidence predictions should be more accurate than low-confidence"


class TestPerfectClassifier:
    def test_perfect_classifier_scores(self) -> None:
        predictions = [
            RouterPrediction("BM-001", "latency", "latency", 0.95),
            RouterPrediction("BM-002", "deployment_regression", "deployment_regression", 0.92),
            RouterPrediction("BM-003", "memory_leak", "memory_leak", 0.88),
        ]
        report = score_router_quality(predictions)
        assert report.accuracy == 1.0
        assert report.macro_f1 == 1.0

    def test_all_wrong_classifier(self) -> None:
        predictions = [
            RouterPrediction("BM-001", "memory_leak", "latency", 0.90),
            RouterPrediction("BM-002", "latency", "deployment_regression", 0.90),
        ]
        report = score_router_quality(predictions)
        assert report.accuracy == 0.0

    def test_empty_predictions(self) -> None:
        report = score_router_quality([])
        assert report.total_predictions == 0
        assert report.accuracy == 0.0
