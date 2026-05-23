"""
Confidence calibration scoring tests.

Validates:
- ECE computation
- Brier score
- Overconfidence/underconfidence detection
- Abstain threshold computation
- Calibration grade assignment
"""

import pytest
from evaluation.benchmark_suite import load_benchmark_suite
from evaluation.scorers.confidence_calibration_scorer import (
    CalibrationBin,
    CalibrationReport,
    build_calibration_data_from_benchmark,
    build_reliability_curve,
    compute_brier_score,
    compute_ece,
    detect_confidence_drift,
    find_abstain_threshold,
    fit_temperature_scale,
    score_confidence_calibration,
)


@pytest.fixture(scope="module")
def suite():
    return load_benchmark_suite()


@pytest.fixture(scope="module")
def calibration_report(suite) -> CalibrationReport:
    confidences, correctness = build_calibration_data_from_benchmark(suite.incidents)
    return score_confidence_calibration(confidences, correctness)


class TestECEComputation:
    def test_perfect_calibration_ece_near_zero(self) -> None:
        confidences = [0.95, 0.95, 0.95, 0.95, 0.95, 0.05, 0.05, 0.05, 0.05, 0.05]
        correctness = [True, True, True, True, True, False, False, False, False, False]
        ece, _ = compute_ece(confidences, correctness)
        assert ece < 0.10, f"Expected low ECE for well-calibrated model, got {ece}"

    def test_overconfident_model_has_high_ece(self) -> None:
        confidences = [0.95] * 10
        correctness = [True, False, True, False, True, False, True, False, True, False]
        ece, _ = compute_ece(confidences, correctness)
        assert ece > 0.20, f"Overconfident model should have high ECE, got {ece}"

    def test_empty_calibration_returns_zero(self) -> None:
        ece, bins = compute_ece([], [])
        assert ece == 0.0
        assert bins == []

    def test_bins_cover_unit_interval(self) -> None:
        confidences = [0.1, 0.3, 0.5, 0.7, 0.9]
        correctness = [False, False, True, True, True]
        _, bins = compute_ece(confidences, correctness)
        assert len(bins) == 10

    def test_bins_have_nonnegative_counts(self) -> None:
        confidences = [0.2, 0.4, 0.6, 0.8]
        correctness = [True, True, False, True]
        _, bins = compute_ece(confidences, correctness)
        for b in bins:
            assert b.count >= 0


class TestBrierScore:
    def test_perfect_predictor_brier_zero(self) -> None:
        confidences = [1.0, 1.0, 1.0]
        correctness = [True, True, True]
        assert compute_brier_score(confidences, correctness) == 0.0

    def test_useless_predictor_brier_high(self) -> None:
        confidences = [1.0, 1.0]
        correctness = [False, False]
        score = compute_brier_score(confidences, correctness)
        assert score == 1.0

    def test_brier_score_in_range(self) -> None:
        confidences = [0.3, 0.7, 0.5, 0.9, 0.1]
        correctness = [False, True, True, False, False]
        score = compute_brier_score(confidences, correctness)
        assert 0.0 <= score <= 1.0

    def test_empty_brier_returns_zero(self) -> None:
        assert compute_brier_score([], []) == 0.0


class TestCalibrationBin:
    def test_overconfident_bin_detected(self) -> None:
        b = CalibrationBin(confidence_low=0.9, confidence_high=1.0, count=10, correct=5)
        assert b.is_overconfident

    def test_underconfident_bin_detected(self) -> None:
        b = CalibrationBin(confidence_low=0.1, confidence_high=0.2, count=10, correct=9)
        assert b.is_underconfident

    def test_well_calibrated_bin_not_flagged(self) -> None:
        b = CalibrationBin(confidence_low=0.7, confidence_high=0.8, count=10, correct=7)
        assert not b.is_overconfident
        assert not b.is_underconfident

    def test_accuracy_correct(self) -> None:
        b = CalibrationBin(confidence_low=0.5, confidence_high=0.6, count=10, correct=6)
        assert abs(b.accuracy - 0.6) < 1e-9

    def test_empty_bin_accuracy_zero(self) -> None:
        b = CalibrationBin(confidence_low=0.5, confidence_high=0.6, count=0, correct=0)
        assert b.accuracy == 0.0


class TestAbstainThreshold:
    def test_abstain_threshold_at_high_confidence(self) -> None:
        confidences = [0.3, 0.5, 0.7, 0.9, 0.9]
        correctness = [False, False, True, True, True]
        threshold = find_abstain_threshold(confidences, correctness, target_accuracy=0.90)
        assert threshold >= 0.7, "Abstain threshold should be high for 90% accuracy target"

    def test_threshold_never_exceeds_one(self) -> None:
        confidences = [0.5, 0.6, 0.7]
        correctness = [False, False, False]
        threshold = find_abstain_threshold(confidences, correctness, target_accuracy=0.90)
        assert threshold <= 1.0


class TestCalibrationReportFromBenchmark:
    def test_report_ece_in_range(self, calibration_report: CalibrationReport) -> None:
        assert 0.0 <= calibration_report.expected_calibration_error <= 1.0

    def test_report_brier_in_range(self, calibration_report: CalibrationReport) -> None:
        assert 0.0 <= calibration_report.brier_score <= 1.0

    def test_report_overconfidence_in_range(self, calibration_report: CalibrationReport) -> None:
        assert 0.0 <= calibration_report.overconfidence_rate <= 1.0

    def test_report_has_bins(self, calibration_report: CalibrationReport) -> None:
        assert len(calibration_report.bins) == 10

    def test_report_has_calibration_grade(self, calibration_report: CalibrationReport) -> None:
        assert calibration_report.calibration_grade in (
            "EXCELLENT",
            "GOOD",
            "FAIR",
            "POOR",
            "FAILING",
        )

    def test_report_has_abstain_threshold(self, calibration_report: CalibrationReport) -> None:
        assert 0.0 <= calibration_report.abstain_recommendation_threshold <= 1.0

    def test_report_has_escalation_threshold(self, calibration_report: CalibrationReport) -> None:
        assert 0.0 <= calibration_report.low_confidence_escalation_threshold <= 1.0

    def test_abstain_threshold_above_escalation_threshold(
        self, calibration_report: CalibrationReport
    ) -> None:
        assert calibration_report.abstain_recommendation_threshold >= (
            calibration_report.low_confidence_escalation_threshold
        ), "Abstain threshold should be >= escalation threshold"

    def test_to_dict_serializable(self, calibration_report: CalibrationReport) -> None:
        import json

        json.dumps(calibration_report.to_dict())

    def test_ece_not_unreasonably_high(self, calibration_report: CalibrationReport) -> None:
        assert calibration_report.expected_calibration_error < 0.40, (
            f"ECE {calibration_report.expected_calibration_error:.3f} is unreasonably high"
        )


class TestPhase44Calibration:
    def test_temperature_scaling_softens_overconfident_predictions(self) -> None:
        confidences = [0.95] * 8 + [0.15] * 2
        correctness = [True, False, True, False, True, False, False, False, True, True]
        temperature = fit_temperature_scale(confidences, correctness)
        assert temperature >= 1.0

    def test_reliability_curve_emits_non_empty_points(self) -> None:
        confidences = [0.2, 0.4, 0.6, 0.8]
        correctness = [False, False, True, True]
        _, bins = compute_ece(confidences, correctness)
        curve = build_reliability_curve(bins)
        assert curve
        assert {"confidence", "accuracy", "gap"} <= curve[0].keys()

    def test_calibration_report_detects_drift_from_baseline(self) -> None:
        report = score_confidence_calibration(
            [0.95, 0.95, 0.95, 0.95],
            [True, False, False, False],
            baseline_ece=0.02,
        )
        assert report.drift_detected is True

    def test_detect_confidence_drift_respects_tolerance(self) -> None:
        assert detect_confidence_drift(0.05, 0.11) is True
        assert detect_confidence_drift(0.05, 0.07) is False
