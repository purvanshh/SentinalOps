"""
Drift monitor for SentinelOps Phase 47.

Watches a stream of accuracy/confidence observations and emits
drift signals when the rolling average deviates from baseline.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass


@dataclass
class DriftSignal:
    """A detected drift event."""

    kind: str  # "accuracy_drop", "confidence_spike", "calibration_drift"
    baseline_value: float
    current_value: float
    delta: float
    severity: str  # "low", "medium", "high"
    observation_count: int

    def summary(self) -> str:
        return (
            f"{self.kind}: baseline={self.baseline_value:.3f} "
            f"current={self.current_value:.3f} delta={self.delta:+.3f} "
            f"severity={self.severity}"
        )


class DriftMonitor:
    """
    Rolling-window drift detector for accuracy and confidence streams.

    Maintains a short-term window (recent observations) and a baseline
    window (earlier observations). Emits DriftSignals when the gap
    between windows exceeds configured thresholds.
    """

    def __init__(
        self,
        short_window: int = 10,
        baseline_window: int = 30,
        accuracy_threshold: float = 0.08,
        calibration_threshold: float = 0.10,
    ) -> None:
        if short_window < 2 or baseline_window < short_window:
            raise ValueError("baseline_window must be >= short_window >= 2")
        self._short_window = short_window
        self._baseline_window = baseline_window
        self._accuracy_threshold = accuracy_threshold
        self._calibration_threshold = calibration_threshold

        self._accuracy_buf: deque[float] = deque(maxlen=baseline_window)
        self._confidence_buf: deque[float] = deque(maxlen=baseline_window)
        self._signals: list[DriftSignal] = []

    def observe(self, accuracy: float, confidence: float) -> list[DriftSignal]:
        """Add one observation and return any newly detected drift signals."""
        self._accuracy_buf.append(accuracy)
        self._confidence_buf.append(confidence)
        new_signals = self._check_drift()
        self._signals.extend(new_signals)
        return new_signals

    def observe_batch(self, observations: list[tuple[float, float]]) -> list[DriftSignal]:
        """Process a batch of (accuracy, confidence) observations."""
        all_signals: list[DriftSignal] = []
        for acc, conf in observations:
            all_signals.extend(self.observe(acc, conf))
        return all_signals

    def all_signals(self) -> list[DriftSignal]:
        return list(self._signals)

    def has_drift(self) -> bool:
        return len(self._signals) > 0

    def latest_signal(self) -> DriftSignal | None:
        return self._signals[-1] if self._signals else None

    def clear_signals(self) -> None:
        self._signals.clear()

    def reset(self) -> None:
        self._accuracy_buf.clear()
        self._confidence_buf.clear()
        self._signals.clear()

    # ------------------------------------------------------------------

    def _check_drift(self) -> list[DriftSignal]:
        n = len(self._accuracy_buf)
        if n < self._short_window + 1:
            return []

        short = list(self._accuracy_buf)[-self._short_window :]
        baseline_end = max(0, n - self._short_window)
        baseline_start = max(0, baseline_end - self._baseline_window)
        baseline = list(self._accuracy_buf)[baseline_start:baseline_end]
        if not baseline:
            return []

        short_acc = sum(short) / len(short)
        base_acc = sum(baseline) / len(baseline)

        short_conf_buf = list(self._confidence_buf)[-self._short_window :]
        base_conf_buf = list(self._confidence_buf)[baseline_start:baseline_end]

        short_conf = sum(short_conf_buf) / len(short_conf_buf)
        base_conf = sum(base_conf_buf) / len(base_conf_buf) if base_conf_buf else short_conf

        signals: list[DriftSignal] = []

        acc_delta = short_acc - base_acc
        if abs(acc_delta) >= self._accuracy_threshold:
            severity = "high" if abs(acc_delta) >= 0.15 else "medium"
            signals.append(
                DriftSignal(
                    kind="accuracy_drop" if acc_delta < 0 else "accuracy_rise",
                    baseline_value=base_acc,
                    current_value=short_acc,
                    delta=acc_delta,
                    severity=severity,
                    observation_count=n,
                )
            )

        cal_error_short = abs(short_acc - short_conf)
        cal_error_base = abs(base_acc - base_conf)
        cal_delta = cal_error_short - cal_error_base
        if abs(cal_delta) >= self._calibration_threshold:
            signals.append(
                DriftSignal(
                    kind="calibration_drift",
                    baseline_value=cal_error_base,
                    current_value=cal_error_short,
                    delta=cal_delta,
                    severity="medium",
                    observation_count=n,
                )
            )

        return signals
