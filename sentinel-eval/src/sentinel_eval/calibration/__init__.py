"""Confidence calibration engine."""


class CalibrationEngine:
    """Calibrates confidence scores against observed outcomes."""

    def calibrate(self, predictions: list[float], outcomes: list[bool]) -> list[float]:
        raise NotImplementedError


class ECECalculator:
    """Expected Calibration Error calculator."""

    def calculate_ece(self, confidences: list[float], accuracies: list[bool], n_bins: int = 10) -> float:
        raise NotImplementedError
