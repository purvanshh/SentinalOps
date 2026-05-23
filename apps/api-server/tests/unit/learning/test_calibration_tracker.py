"""Tests for ConfidenceDriftTracker (Phase 46)."""

from __future__ import annotations

from learning.calibration_tracker import ConfidenceDriftTracker, ConfidenceSample


def _sample(
    incident_id: str = "INC-001",
    confidence: float = 0.80,
    correct: bool = True,
    category: str = "performance",
) -> ConfidenceSample:
    return ConfidenceSample(
        incident_id=incident_id,
        stated_confidence=confidence,
        was_correct=correct,
        category=category,
    )


def _overconfident_batch(n: int = 10) -> list[ConfidenceSample]:
    """High confidence, low accuracy → overconfident."""
    return [
        ConfidenceSample(
            incident_id=f"INC-{i:03d}",
            stated_confidence=0.90,
            was_correct=False,
            category="performance",
        )
        for i in range(n)
    ]


def _calibrated_batch(n: int = 10) -> list[ConfidenceSample]:
    """Confidence=1.0 with all correct → perfectly calibrated."""
    return [
        ConfidenceSample(
            incident_id=f"INC-{i:03d}",
            stated_confidence=1.0,
            was_correct=True,
            category="performance",
        )
        for i in range(n)
    ]


def _accurate_batch(n: int = 10) -> list[ConfidenceSample]:
    """80% correct at 80% confidence → calibrated."""
    return [
        ConfidenceSample(
            incident_id=f"INC-{i:03d}",
            stated_confidence=0.80,
            was_correct=(i % 5 != 0),  # 80% correct
            category="performance",
        )
        for i in range(n)
    ]


class TestConfidenceDriftTracker:
    def test_initial_no_drift(self):
        tracker = ConfidenceDriftTracker()
        assert tracker.current_drift() is None

    def test_insufficient_samples_returns_none(self):
        tracker = ConfidenceDriftTracker()
        tracker.record(_sample())
        assert tracker.current_drift() is None

    def test_five_samples_produces_drift(self):
        tracker = ConfidenceDriftTracker()
        tracker.record_batch(_accurate_batch(5))
        drift = tracker.current_drift()
        assert drift is not None

    def test_overconfident_drift_detected(self):
        tracker = ConfidenceDriftTracker()
        tracker.record_batch(_overconfident_batch(10))
        drift = tracker.current_drift()
        assert drift is not None
        assert drift.drift_direction == "overconfident"

    def test_calibrated_drift_when_accurate(self):
        tracker = ConfidenceDriftTracker()
        tracker.record_batch(_calibrated_batch(10))
        drift = tracker.current_drift()
        assert drift is not None
        assert drift.drift_direction == "calibrated"

    def test_underconfident_drift_detected(self):
        tracker = ConfidenceDriftTracker()
        samples = [
            ConfidenceSample(
                incident_id=f"INC-{i:03d}",
                stated_confidence=0.40,  # low stated confidence
                was_correct=True,  # but always correct
                category="performance",
            )
            for i in range(10)
        ]
        tracker.record_batch(samples)
        drift = tracker.current_drift()
        assert drift is not None
        assert drift.drift_direction == "underconfident"

    def test_overconfident_correction_is_negative(self):
        tracker = ConfidenceDriftTracker()
        tracker.record_batch(_overconfident_batch(10))
        drift = tracker.current_drift()
        assert drift is not None
        assert drift.correction_recommendation < 0.0

    def test_correction_bounded_negative(self):
        tracker = ConfidenceDriftTracker()
        tracker.record_batch(_overconfident_batch(50))
        drift = tracker.current_drift()
        assert drift is not None
        assert drift.correction_recommendation >= -0.15

    def test_calibration_score_high_when_accurate(self):
        tracker = ConfidenceDriftTracker()
        tracker.record_batch(_calibrated_batch(10))
        score = tracker.calibration_score()
        assert score >= 0.90

    def test_calibration_score_low_when_overconfident(self):
        tracker = ConfidenceDriftTracker()
        tracker.record_batch(_overconfident_batch(10))
        score = tracker.calibration_score()
        assert score < 0.50

    def test_calibration_score_neutral_when_no_data(self):
        tracker = ConfidenceDriftTracker()
        assert tracker.calibration_score() == 0.5

    def test_is_overconfident_flag(self):
        tracker = ConfidenceDriftTracker()
        tracker.record_batch(_overconfident_batch(10))
        assert tracker.is_overconfident() is True

    def test_is_not_overconfident_when_accurate(self):
        tracker = ConfidenceDriftTracker()
        tracker.record_batch(_accurate_batch(10))
        assert tracker.is_overconfident() is False

    def test_correction_for_category(self):
        tracker = ConfidenceDriftTracker()
        samples = _overconfident_batch(10)
        tracker.record_batch(samples)
        correction = tracker.correction_for_category("performance")
        assert correction < 0.0

    def test_correction_for_unknown_category_is_zero(self):
        tracker = ConfidenceDriftTracker()
        tracker.record_batch(_accurate_batch(10))
        correction = tracker.correction_for_category("unknown_category")
        assert correction == 0.0

    def test_category_breakdown(self):
        tracker = ConfidenceDriftTracker()
        perf_samples = [
            ConfidenceSample(
                incident_id=f"P{i}",
                stated_confidence=0.80,
                was_correct=True,
                category="performance",
            )
            for i in range(3)
        ]
        avail_samples = [
            ConfidenceSample(
                incident_id=f"A{i}",
                stated_confidence=0.70,
                was_correct=False,
                category="availability",
            )
            for i in range(3)
        ]
        tracker.record_batch(perf_samples + avail_samples)
        breakdown = tracker.category_breakdown()
        assert "performance" in breakdown
        assert "availability" in breakdown

    def test_total_samples(self):
        tracker = ConfidenceDriftTracker()
        tracker.record_batch(_accurate_batch(7))
        assert tracker.total_samples() == 7

    def test_window_computed_on_full_window(self):
        tracker = ConfidenceDriftTracker(window_size=5)
        tracker.record_batch(_accurate_batch(10))
        windows = tracker.all_windows()
        assert len(windows) == 2

    def test_drift_window_to_dict(self):
        tracker = ConfidenceDriftTracker()
        tracker.record_batch(_accurate_batch(5))
        drift = tracker.current_drift()
        assert drift is not None
        d = drift.to_dict()
        for key in [
            "window_id",
            "sample_count",
            "mean_stated_confidence",
            "actual_accuracy",
            "calibration_error",
            "drift_direction",
            "correction_recommendation",
        ]:
            assert key in d
