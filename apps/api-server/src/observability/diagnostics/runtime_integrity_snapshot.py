"""Runtime integrity snapshot — point-in-time system health capture."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


@dataclass
class IntegrityReport:
    snapshot_id: str
    captured_at: float
    system_state: str  # "nominal", "degraded", "critical"
    confidence_health: dict[str, Any]
    reasoning_health: dict[str, Any]
    telemetry_health: dict[str, Any]
    active_alerts: list[dict[str, Any]]
    overall_integrity_score: float
    operator_summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "captured_at": self.captured_at,
            "system_state": self.system_state,
            "confidence_health": self.confidence_health,
            "reasoning_health": self.reasoning_health,
            "telemetry_health": self.telemetry_health,
            "active_alerts": self.active_alerts,
            "overall_integrity_score": self.overall_integrity_score,
            "operator_summary": self.operator_summary,
        }

    def prometheus_metrics(self) -> str:
        lines = [
            f"sentinelops_integrity_score {self.overall_integrity_score}",
            f'sentinelops_system_state{{state="{self.system_state}"}} 1',
            f"sentinelops_active_alerts {len(self.active_alerts)}",
        ]
        return "\n".join(lines) + "\n"


class RuntimeIntegritySnapshot:
    """Capture and evaluate a point-in-time integrity snapshot of the runtime."""

    def __init__(self) -> None:
        self._snapshot_counter = 0
        self._history: list[IntegrityReport] = []

    def capture(
        self,
        confidence_monitor: Any = None,
        collapse_detector: Any = None,
        telemetry_monitor: Any = None,
    ) -> IntegrityReport:
        self._snapshot_counter += 1
        snapshot_id = f"snap-{self._snapshot_counter:04d}"

        confidence_health = (
            confidence_monitor.current_stats()
            if confidence_monitor is not None
            else {"status": "monitor_not_attached"}
        )
        reasoning_health = (
            collapse_detector.summary()
            if collapse_detector is not None
            else {"status": "detector_not_attached"}
        )
        telemetry_health = (
            telemetry_monitor.current_health()
            if telemetry_monitor is not None
            else {"status": "monitor_not_attached"}
        )

        active_alerts = self._collect_alerts(confidence_monitor, collapse_detector)
        integrity_score = self._compute_integrity(
            confidence_health, reasoning_health, active_alerts
        )
        system_state = self._classify_state(integrity_score, active_alerts)
        summary = self._build_summary(snapshot_id, system_state, integrity_score, active_alerts)

        report = IntegrityReport(
            snapshot_id=snapshot_id,
            captured_at=time.time(),
            system_state=system_state,
            confidence_health=confidence_health,
            reasoning_health=reasoning_health,
            telemetry_health=telemetry_health,
            active_alerts=active_alerts,
            overall_integrity_score=round(integrity_score, 4),
            operator_summary=summary,
        )
        self._history.append(report)
        return report

    def history(self) -> list[IntegrityReport]:
        return list(self._history)

    def _collect_alerts(
        self, confidence_monitor: Any, collapse_detector: Any
    ) -> list[dict[str, Any]]:
        alerts: list[dict[str, Any]] = []
        if collapse_detector is not None:
            summary = collapse_detector.summary()
            if summary.get("total_collapse_events", 0) > 0:
                alerts.append(
                    {
                        "source": "reasoning",
                        "count": summary["total_collapse_events"],
                        "severity": "high",
                    }
                )
        return alerts

    def _compute_integrity(
        self,
        confidence_health: dict[str, Any],
        reasoning_health: dict[str, Any],
        alerts: list[dict[str, Any]],
    ) -> float:
        score = 1.0
        mean_conf = confidence_health.get("mean")
        if isinstance(mean_conf, (int, float)):
            if mean_conf < 0.20 or mean_conf > 0.90:
                score -= 0.20
        collapse_rate = reasoning_health.get("collapse_rate_last_100", 0.0)
        if isinstance(collapse_rate, (int, float)):
            score -= min(0.40, float(collapse_rate) * 0.10)
        score -= min(0.30, len(alerts) * 0.10)
        return max(0.0, score)

    def _classify_state(self, score: float, alerts: list[dict[str, Any]]) -> str:
        critical = any(a.get("severity") == "critical" for a in alerts)
        if score < 0.40 or critical:
            return "critical"
        if score < 0.70:
            return "degraded"
        return "nominal"

    def _build_summary(
        self, snapshot_id: str, state: str, score: float, alerts: list[dict[str, Any]]
    ) -> str:
        return (
            f"[{snapshot_id}] System state: {state.upper()} | "
            f"Integrity: {score:.2f} | Active alerts: {len(alerts)}"
        )
