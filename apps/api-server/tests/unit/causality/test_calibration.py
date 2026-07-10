from __future__ import annotations

from causality.calibration import (
    IsotonicCalibrator,
    TemperatureCalibrator,
    build_reliability_diagram_data,
    split_calibration_data,
)


def test_temperature_calibrator() -> None:
    calibrator = TemperatureCalibrator()
    assert not calibrator.fitted

    # Unfitted predict should act as identity
    assert calibrator.predict(0.7) == 0.7

    # Fit with some simulated data (underconfident model: high correctness on low conf)
    confidences = [0.3, 0.4, 0.5, 0.3, 0.4, 0.5]
    correctness = [True, True, True, True, True, True]

    calibrator.fit(confidences, correctness)
    assert calibrator.fitted
    assert calibrator.temperature != 1.0

    # Predictions should be scaled up due to high correctness
    assert calibrator.predict(0.3) > 0.3


def test_isotonic_calibrator() -> None:
    calibrator = IsotonicCalibrator()
    assert not calibrator.fitted

    # Fit with non-monotonic correctness rates
    confidences = [0.1, 0.2, 0.3, 0.4, 0.5]
    correctness = [False, True, False, True, True]

    calibrator.fit(confidences, correctness)
    assert calibrator.fitted

    # Verify monotonicity of predictions
    p1 = calibrator.predict(0.1)
    p2 = calibrator.predict(0.2)
    p3 = calibrator.predict(0.3)
    p4 = calibrator.predict(0.4)
    p5 = calibrator.predict(0.5)

    assert p1 <= p2 <= p3 <= p4 <= p5


def test_split_calibration_data() -> None:
    confidences = [0.1] * 10
    correctness = [True] * 10
    split = split_calibration_data(confidences, correctness, cal_fraction=0.2)

    # Size check: 10 * 0.2 = 2 calibration items, 2 test items, 6 train items
    assert len(split.train_confidences) == 6
    assert len(split.cal_confidences) == 2
    assert len(split.test_confidences) == 2


def test_build_reliability_diagram_data() -> None:
    confidences = [0.15, 0.25, 0.35]
    correctness = [True, False, True]
    data = build_reliability_diagram_data(confidences, correctness, n_bins=10)

    # Check bins details
    assert len(data) > 0
    first_bin = data[0]
    assert "bin_center" in first_bin
    assert "accuracy" in first_bin
    assert "confidence" in first_bin
    assert "count" in first_bin
