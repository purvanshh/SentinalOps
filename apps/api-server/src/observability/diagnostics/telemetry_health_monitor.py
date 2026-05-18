"""Telemetry health monitor — tracks completeness, freshness, and anomaly rate."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Any


@dataclass
class TelemetryHealthReport:
    total_samples: int
    corrupt_samples: int
    missing_field_rate: float
    impossible_value_rate: float
    staleness_seconds: float
    health_score: float
    status: str  # "healthy", "degraded", "corrupt"
    recommendations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_samples": self.total_samples,
            "corrupt_samples": self.corrupt_samples,
            "missing_field_rate": self.missing_field_rate,
            "impossible_value_rate": self.impossible_value_rate,
            "staleness_seconds": self.staleness_seconds,
            "health_score": self.health_score,
            "status": self.status,
            "recommendations": self.recommendations,
        }

    def prometheus_metrics(self) -> str:
        lines = [
            f"sentinelops_telemetry_health_score {self.health_score}",
            f"sentinelops_telemetry_corrupt_samples_total {self.corrupt_samples}",
            f"sentinelops_telemetry_missing_field_rate {self.missing_field_rate}",
            f"sentinelops_telemetry_staleness_seconds {self.staleness_seconds}",
        ]
        return "\n".join(lines) + "\n"


_REQUIRED_METRIC_KEYS = {"error_rate", "latency_p99"}
_IMPOSSIBLE_CHECKS = [
    ("error_rate", lambda v: v < 0.0 or v > 1.0),
    ("success_rate", lambda v: v < 0.0 or v > 1.0),
    ("latency_p99", lambda v: v < 0.0),
    ("requests_per_second", lambda v: v < 0.0),
]


class TelemetryHealthMonitor:
    """Track telemetry quality across a sliding window of samples."""

    def __init__(self, window_size: int = 100) -> None:
        self._window: deque[dict[str, Any]] = deque(maxlen=window_size)
        self._corrupt_count = 0
        self._total_count = 0
        self._last_sample_at: float | None = None

    def record(self, sample: dict[str, Any]) -> bool:
        """Record a telemetry sample. Returns False if sample is detected as corrupt."""
        self._total_count += 1
        self._last_sample_at = time.time()
        corrupt = self._is_corrupt(sample)
        if corrupt:
            self._corrupt_count += 1
        self._window.append({"sample": sample, "corrupt": corrupt, "ts": self._last_sample_at})
        return not corrupt

    def current_health(self) -> dict[str, Any]:
        report = self.generate_report()
        return report.to_dict()

    def generate_report(self) -> TelemetryHealthReport:
        window = list(self._window)
        total = len(window)
        corrupt = sum(1 for w in window if w["corrupt"])
        missing_fields = sum(1 for w in window if self._has_missing_fields(w["sample"]))
        impossible = sum(1 for w in window if self._has_impossible_values(w["sample"]))

        missing_rate = round(missing_fields / total, 4) if total else 0.0
        impossible_rate = round(impossible / total, 4) if total else 0.0
        corrupt_rate = round(corrupt / total, 4) if total else 0.0

        staleness = 0.0
        if self._last_sample_at:
            staleness = round(time.time() - self._last_sample_at, 1)

        health_score = max(
            0.0,
            1.0 - (corrupt_rate * 0.50) - (missing_rate * 0.25) - (impossible_rate * 0.25),
        )

        if health_score >= 0.80:
            status = "healthy"
        elif health_score >= 0.50:
            status = "degraded"
        else:
            status = "corrupt"

        recommendations = self._recommendations(corrupt_rate, missing_rate, impossible_rate, staleness)

        return TelemetryHealthReport(
            total_samples=self._total_count,
            corrupt_samples=self._corrupt_count,
            missing_field_rate=missing_rate,
            impossible_value_rate=impossible_rate,
            staleness_seconds=staleness,
            health_score=round(health_score, 4),
            status=status,
            recommendations=recommendations,
        )

    def _is_corrupt(self, sample: dict[str, Any]) -> bool:
        return self._has_impossible_values(sample)

    def _has_missing_fields(self, sample: dict[str, Any]) -> bool:
        metrics = sample.get("metrics", {})
        return not all(k in metrics for k in _REQUIRED_METRIC_KEYS)

    def _has_impossible_values(self, sample: dict[str, Any]) -> bool:
        metrics = sample.get("metrics", {})
        for key, check in _IMPOSSIBLE_CHECKS:
            val = metrics.get(key)
            if val is not None:
                try:
                    if check(float(val)):
                        return True
                except (TypeError, ValueError):
                    return True
        return False

    def _recommendations(
        self, corrupt: float, missing: float, impossible: float, staleness: float
    ) -> list[str]:
        recs: list[str] = []
        if corrupt > 0.10:
            recs.append(f"High corrupt rate {corrupt:.0%} — investigate telemetry pipeline")
        if missing > 0.20:
            recs.append(f"Missing fields in {missing:.0%} of samples — check metric exporters")
        if impossible > 0.05:
            recs.append(f"Impossible values in {impossible:.0%} of samples — possible metric poisoning")
        if staleness > 60.0:
            recs.append(f"Last sample {staleness:.0f}s ago — telemetry stream may have stopped")
        return recs
