"""
Longitudinal evaluation metrics for SentinelOps Phase 47.

Computes multi-window accuracy, drift detection, and trend scoring
over time-ordered evaluation runs. Detects performance degradation
and confidence calibration drift across operational windows.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any

_SEVERITY_RANK: dict[str, int] = {
    "critical": 4,
    "error": 3,
    "warning": 2,
    "info": 1,
    "debug": 0,
}


@dataclass
class WindowMetrics:
    """Metrics computed over one sliding evaluation window."""

    window_index: int
    window_size: int
    accuracy: float
    mean_confidence: float
    calibration_error: float  # |accuracy - mean_confidence|
    severity_weighted_accuracy: float
    completeness_weighted_accuracy: float

    @property
    def is_overconfident(self) -> bool:
        return self.mean_confidence > self.accuracy + 0.10

    @property
    def is_underconfident(self) -> bool:
        return self.accuracy > self.mean_confidence + 0.10

    @property
    def calibration_label(self) -> str:
        if self.is_overconfident:
            return "overconfident"
        if self.is_underconfident:
            return "underconfident"
        return "calibrated"


@dataclass
class DriftReport:
    """Drift detection result comparing early vs. late windows."""

    early_accuracy: float
    late_accuracy: float
    accuracy_delta: float
    early_calibration_error: float
    late_calibration_error: float
    calibration_delta: float
    drift_detected: bool
    drift_direction: str  # "degrading", "improving", "stable"

    _DRIFT_THRESHOLD: float = 0.05

    def summary(self) -> str:
        return (
            f"drift={self.drift_direction} "
            f"acc_delta={self.accuracy_delta:+.3f} "
            f"cal_delta={self.calibration_delta:+.3f}"
        )


@dataclass
class EvaluationRecord:
    """One scored evaluation result, used as input to longitudinal metrics."""

    sample_id: str
    correct: bool
    confidence: float
    severity: str = "info"
    telemetry_completeness: float = 1.0
    timestamp_iso: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def severity_weight(self) -> float:
        return _SEVERITY_RANK.get(self.severity, 1) / 4.0


@dataclass
class LongitudinalReport:
    """Full longitudinal evaluation report across all windows."""

    total_records: int
    num_windows: int
    window_size: int
    windows: list[WindowMetrics]
    overall_accuracy: float
    overall_calibration_error: float
    drift: DriftReport | None
    trend: str  # "improving", "degrading", "stable", "volatile"

    def worst_window(self) -> WindowMetrics | None:
        if not self.windows:
            return None
        return min(self.windows, key=lambda w: w.accuracy)

    def best_window(self) -> WindowMetrics | None:
        if not self.windows:
            return None
        return max(self.windows, key=lambda w: w.accuracy)


class LongitudinalEvaluator:
    """
    Computes longitudinal metrics over time-ordered evaluation records.

    Sliding-window analysis detects accuracy drift and calibration changes
    across operational windows without requiring ground-truth labels beyond
    pass/fail correctness indicators.
    """

    def __init__(self, window_size: int = 20) -> None:
        if window_size < 2:
            raise ValueError("window_size must be >= 2")
        self._window_size = window_size
        self._records: list[EvaluationRecord] = []

    def ingest(self, record: EvaluationRecord) -> None:
        self._records.append(record)

    def ingest_batch(self, records: list[EvaluationRecord]) -> None:
        self._records.extend(records)

    def compute(self) -> LongitudinalReport:
        records = self._records
        if not records:
            return self._empty_report()

        windows = self._compute_windows(records)
        overall_accuracy = sum(1 for r in records if r.correct) / len(records)
        mean_conf = sum(r.confidence for r in records) / len(records)
        overall_cal_error = abs(overall_accuracy - mean_conf)
        drift = self._detect_drift(windows)
        trend = self._compute_trend([w.accuracy for w in windows])

        return LongitudinalReport(
            total_records=len(records),
            num_windows=len(windows),
            window_size=self._window_size,
            windows=windows,
            overall_accuracy=overall_accuracy,
            overall_calibration_error=overall_cal_error,
            drift=drift,
            trend=trend,
        )

    def reset(self) -> None:
        self._records.clear()

    # ------------------------------------------------------------------

    def _compute_windows(self, records: list[EvaluationRecord]) -> list[WindowMetrics]:
        windows: list[WindowMetrics] = []
        step = max(1, self._window_size // 2)
        i = 0
        win_idx = 0
        while i < len(records):
            window = records[i : i + self._window_size]
            if not window:
                break
            wm = self._window_metrics(window, win_idx)
            windows.append(wm)
            i += step
            win_idx += 1
        return windows

    def _window_metrics(self, records: list[EvaluationRecord], idx: int) -> WindowMetrics:
        n = len(records)
        accuracy = sum(1 for r in records if r.correct) / n
        mean_conf = sum(r.confidence for r in records) / n

        total_weight = sum(r.severity_weight for r in records)
        if total_weight > 0:
            severity_acc = sum(r.severity_weight for r in records if r.correct) / total_weight
        else:
            severity_acc = accuracy

        total_comp = sum(r.telemetry_completeness for r in records)
        if total_comp > 0:
            comp_acc = sum(r.telemetry_completeness for r in records if r.correct) / total_comp
        else:
            comp_acc = accuracy

        return WindowMetrics(
            window_index=idx,
            window_size=n,
            accuracy=accuracy,
            mean_confidence=mean_conf,
            calibration_error=abs(accuracy - mean_conf),
            severity_weighted_accuracy=severity_acc,
            completeness_weighted_accuracy=comp_acc,
        )

    def _detect_drift(self, windows: list[WindowMetrics]) -> DriftReport | None:
        if len(windows) < 2:
            return None
        half = max(1, len(windows) // 2)
        early = windows[:half]
        late = windows[half:]

        early_acc = statistics.mean(w.accuracy for w in early)
        late_acc = statistics.mean(w.accuracy for w in late)
        early_cal = statistics.mean(w.calibration_error for w in early)
        late_cal = statistics.mean(w.calibration_error for w in late)

        acc_delta = late_acc - early_acc
        cal_delta = late_cal - early_cal

        threshold = DriftReport._DRIFT_THRESHOLD
        drift_detected = abs(acc_delta) > threshold
        if drift_detected:
            direction = "improving" if acc_delta > 0 else "degrading"
        else:
            direction = "stable"

        return DriftReport(
            early_accuracy=early_acc,
            late_accuracy=late_acc,
            accuracy_delta=acc_delta,
            early_calibration_error=early_cal,
            late_calibration_error=late_cal,
            calibration_delta=cal_delta,
            drift_detected=drift_detected,
            drift_direction=direction,
        )

    def _compute_trend(self, accuracies: list[float]) -> str:
        if len(accuracies) < 2:
            return "stable"
        increases = sum(1 for a, b in zip(accuracies, accuracies[1:], strict=False) if b > a + 0.01)
        decreases = sum(1 for a, b in zip(accuracies, accuracies[1:], strict=False) if b < a - 0.01)
        total_transitions = len(accuracies) - 1
        volatile_threshold = 0.6 * total_transitions

        if increases + decreases > volatile_threshold and increases > 0 and decreases > 0:
            return "volatile"
        if increases > decreases and increases >= total_transitions * 0.5:
            return "improving"
        if decreases > increases and decreases >= total_transitions * 0.5:
            return "degrading"
        return "stable"

    def _empty_report(self) -> LongitudinalReport:
        return LongitudinalReport(
            total_records=0,
            num_windows=0,
            window_size=self._window_size,
            windows=[],
            overall_accuracy=0.0,
            overall_calibration_error=0.0,
            drift=None,
            trend="stable",
        )
