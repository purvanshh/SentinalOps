"""
Confidence Drift Tracker for SentinelOps Phase 46.

Detects systematic over-confidence or under-confidence in the AI system
by comparing stated confidence values against actual prediction accuracy.

Tracked per drift window:
  - expected_accuracy: mean stated confidence
  - actual_accuracy: fraction of predictions that were correct
  - calibration_error: |expected - actual|
  - drift_direction: "overconfident", "underconfident", or "calibrated"
  - correction_recommendation: bounded adjustment to apply

Design constraints:
  - Drift detection requires at least MIN_WINDOW_SIZE samples.
  - Correction recommendations are bounded to [-0.15, 0.10].
  - Drift direction is surfaced as a warning, not a hard correction.
  - Historical windows are retained for audit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_MIN_WINDOW_SIZE = 5
_OVERCONFIDENCE_THRESHOLD = 0.10  # expected > actual by this margin
_UNDERCONFIDENCE_THRESHOLD = 0.10  # actual > expected by this margin
_MAX_POSITIVE_CORRECTION = 0.10
_MAX_NEGATIVE_CORRECTION = -0.15


@dataclass
class ConfidenceSample:
    """Single confidence vs. accuracy data point."""

    incident_id: str
    stated_confidence: float
    was_correct: bool
    category: str = ""
    mechanism_id: str | None = None


@dataclass
class DriftWindow:
    """Calibration statistics over a sliding window of samples."""

    window_id: str
    sample_count: int
    mean_stated_confidence: float
    actual_accuracy: float
    calibration_error: float
    drift_direction: str  # "overconfident" | "underconfident" | "calibrated"
    correction_recommendation: float  # bounded
    sample_size_adequate: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "window_id": self.window_id,
            "sample_count": self.sample_count,
            "mean_stated_confidence": round(self.mean_stated_confidence, 4),
            "actual_accuracy": round(self.actual_accuracy, 4),
            "calibration_error": round(self.calibration_error, 4),
            "drift_direction": self.drift_direction,
            "correction_recommendation": round(self.correction_recommendation, 4),
            "sample_size_adequate": self.sample_size_adequate,
        }


class ConfidenceDriftTracker:
    """
    Tracks confidence calibration drift over time.

    Compares stated AI confidence against actual prediction outcomes
    to detect and report systematic over- or under-confidence.
    """

    def __init__(self, window_size: int = 20) -> None:
        self._window_size = max(window_size, _MIN_WINDOW_SIZE)
        self._samples: list[ConfidenceSample] = []
        self._windows: list[DriftWindow] = []
        self._window_counter = 0

    def record(self, sample: ConfidenceSample) -> None:
        """Record a single confidence vs. accuracy sample."""
        self._samples.append(sample)
        # Compute a new window every time we fill a window
        if len(self._samples) >= self._window_size and len(self._samples) % self._window_size == 0:
            window_samples = self._samples[-self._window_size :]
            self._windows.append(self._compute_window(window_samples))

    def record_batch(self, samples: list[ConfidenceSample]) -> None:
        for s in samples:
            self.record(s)

    def current_drift(self) -> DriftWindow | None:
        """Return the most recently computed drift window, or None if insufficient data."""
        if self._windows:
            return self._windows[-1]
        samples = self._samples
        if len(samples) < _MIN_WINDOW_SIZE:
            return None
        return self._compute_window(samples)

    def all_windows(self) -> list[DriftWindow]:
        return list(self._windows)

    def is_overconfident(self) -> bool:
        w = self.current_drift()
        return w is not None and w.drift_direction == "overconfident"

    def is_underconfident(self) -> bool:
        w = self.current_drift()
        return w is not None and w.drift_direction == "underconfident"

    def correction_for_category(self, category: str) -> float:
        """
        Return a bounded confidence correction for a specific incident category.

        Computed from samples in that category only.
        Bounded to [_MAX_NEGATIVE_CORRECTION, _MAX_POSITIVE_CORRECTION].
        """
        cat_samples = [s for s in self._samples if s.category == category]
        if len(cat_samples) < _MIN_WINDOW_SIZE:
            return 0.0
        w = self._compute_window(cat_samples)
        return w.correction_recommendation

    def calibration_score(self) -> float:
        """
        Overall calibration quality score.

        1.0 = perfectly calibrated, 0.0 = maximally miscalibrated.
        Returns 0.5 when insufficient data.
        """
        if not self._windows:
            if len(self._samples) < _MIN_WINDOW_SIZE:
                return 0.5
            w = self._compute_window(self._samples)
            return round(1.0 - w.calibration_error, 4)
        errors = [w.calibration_error for w in self._windows]
        mean_err = sum(errors) / len(errors)
        return round(max(0.0, 1.0 - mean_err), 4)

    def total_samples(self) -> int:
        return len(self._samples)

    def category_breakdown(self) -> dict[str, dict[str, float]]:
        """Return calibration stats per incident category."""
        categories: dict[str, list[ConfidenceSample]] = {}
        for s in self._samples:
            categories.setdefault(s.category, []).append(s)
        result: dict[str, dict[str, float]] = {}
        for cat, samples in categories.items():
            if len(samples) < 2:
                continue
            mean_conf = sum(s.stated_confidence for s in samples) / len(samples)
            actual_acc = sum(1 for s in samples if s.was_correct) / len(samples)
            result[cat] = {
                "mean_confidence": round(mean_conf, 4),
                "actual_accuracy": round(actual_acc, 4),
                "calibration_error": round(abs(mean_conf - actual_acc), 4),
                "sample_count": len(samples),
            }
        return result

    # ------------------------------------------------------------------
    # Internal window computation
    # ------------------------------------------------------------------

    def _compute_window(self, samples: list[ConfidenceSample]) -> DriftWindow:
        self._window_counter += 1
        n = len(samples)
        mean_conf = sum(s.stated_confidence for s in samples) / n
        actual_acc = sum(1 for s in samples if s.was_correct) / n
        error = abs(mean_conf - actual_acc)

        if mean_conf > actual_acc + _OVERCONFIDENCE_THRESHOLD:
            direction = "overconfident"
            # Suggest reducing confidence: negative correction
            raw_correction = -(mean_conf - actual_acc) * 0.5
            correction = max(_MAX_NEGATIVE_CORRECTION, raw_correction)
        elif actual_acc > mean_conf + _UNDERCONFIDENCE_THRESHOLD:
            direction = "underconfident"
            # Suggest modest positive correction — capped conservatively
            raw_correction = (actual_acc - mean_conf) * 0.3
            correction = min(_MAX_POSITIVE_CORRECTION, raw_correction)
        else:
            direction = "calibrated"
            correction = 0.0

        return DriftWindow(
            window_id=f"window_{self._window_counter:04d}",
            sample_count=n,
            mean_stated_confidence=round(mean_conf, 4),
            actual_accuracy=round(actual_acc, 4),
            calibration_error=round(error, 4),
            drift_direction=direction,
            correction_recommendation=round(correction, 4),
            sample_size_adequate=n >= _MIN_WINDOW_SIZE,
        )
