"""Confidence drift monitor — detects systematic bias or instability in confidence scores."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DriftAlert:
    alert_type: str
    severity: str
    message: str
    window_size: int
    mean_confidence: float
    std_confidence: float
    triggered_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "alert_type": self.alert_type,
            "severity": self.severity,
            "message": self.message,
            "window_size": self.window_size,
            "mean_confidence": self.mean_confidence,
            "std_confidence": self.std_confidence,
            "triggered_at": self.triggered_at,
        }

    def prometheus_labels(self) -> str:
        return f'alert_type="{self.alert_type}",severity="{self.severity}"'


_DRIFT_RULES = [
    # (alert_type, condition_fn, severity, message_template)
    (
        "confidence_inflation",
        lambda mean, std: mean > 0.85 and std < 0.05,
        "warning",
        "Mean confidence {mean:.3f} is suspiciously high with low variance {std:.3f}",
    ),
    (
        "confidence_collapse",
        lambda mean, std: mean < 0.20,
        "critical",
        "Mean confidence {mean:.3f} is critically low — system may be refusing all attribution",
    ),
    (
        "confidence_instability",
        lambda mean, std: std > 0.30,
        "warning",
        "Confidence std {std:.3f} indicates high instability across recent incidents",
    ),
    (
        "confidence_floor_violation",
        lambda mean, std: mean < 0.05,
        "critical",
        "Mean confidence {mean:.3f} below minimum floor 0.05 — reasoning breakdown suspected",
    ),
]


class ConfidenceDriftMonitor:
    """Sliding-window monitor for confidence score health.

    Exposes Prometheus-compatible metrics and operator-readable summaries.
    """

    def __init__(self, window_size: int = 50) -> None:
        self._window: deque[float] = deque(maxlen=window_size)
        self._window_size = window_size
        self._alerts: list[DriftAlert] = []

    def record(self, confidence: float) -> list[DriftAlert]:
        if not (0.0 <= confidence <= 1.0):
            raise ValueError(f"Confidence must be in [0,1], got {confidence}")
        self._window.append(confidence)
        new_alerts = self._check_rules()
        self._alerts.extend(new_alerts)
        return new_alerts

    def current_stats(self) -> dict[str, Any]:
        if not self._window:
            return {"status": "no_data", "observations": 0}
        values = list(self._window)
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        std = variance**0.5
        return {
            "observations": len(values),
            "mean": round(mean, 4),
            "std": round(std, 4),
            "min": round(min(values), 4),
            "max": round(max(values), 4),
            "window_size": self._window_size,
            "recent_alerts": len(self._alerts),
        }

    def prometheus_metrics(self) -> str:
        stats = self.current_stats()
        if stats.get("status") == "no_data":
            return "# no confidence data recorded yet\n"
        lines = [
            f"sentinelops_confidence_mean {stats['mean']}",
            f"sentinelops_confidence_std {stats['std']}",
            f"sentinelops_confidence_min {stats['min']}",
            f"sentinelops_confidence_max {stats['max']}",
            f"sentinelops_confidence_observations {stats['observations']}",
            f"sentinelops_confidence_alerts_total {stats['recent_alerts']}",
        ]
        return "\n".join(lines) + "\n"

    def operator_summary(self) -> str:
        stats = self.current_stats()
        if stats.get("status") == "no_data":
            return "No confidence data recorded."
        recent_alerts = [a for a in self._alerts[-5:]]
        alert_lines = "\n".join(f"  [{a.severity.upper()}] {a.message}" for a in recent_alerts)
        return (
            f"Confidence Monitor | obs={stats['observations']} mean={stats['mean']:.3f} "
            f"std={stats['std']:.3f} min={stats['min']:.3f} max={stats['max']:.3f}\n"
            f"Recent alerts ({len(recent_alerts)}):\n{alert_lines or '  None'}"
        )

    def reset(self) -> None:
        self._window.clear()
        self._alerts.clear()

    def _check_rules(self) -> list[DriftAlert]:
        if len(self._window) < 5:
            return []
        values = list(self._window)
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        std = variance**0.5

        triggered = []
        for alert_type, condition, severity, msg_template in _DRIFT_RULES:
            if condition(mean, std):
                triggered.append(
                    DriftAlert(
                        alert_type=alert_type,
                        severity=severity,
                        message=msg_template.format(mean=mean, std=std),
                        window_size=len(values),
                        mean_confidence=round(mean, 4),
                        std_confidence=round(std, 4),
                    )
                )
        return triggered
