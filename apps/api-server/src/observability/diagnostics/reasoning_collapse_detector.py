"""Reasoning collapse detector — identifies when the system's output degrades structurally."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CollapseEvent:
    collapse_type: str
    severity: str
    incident_id: str
    description: str
    evidence: dict[str, Any]
    detected_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "collapse_type": self.collapse_type,
            "severity": self.severity,
            "incident_id": self.incident_id,
            "description": self.description,
            "evidence": self.evidence,
            "detected_at": self.detected_at,
        }


_COLLAPSE_CHECKS = [
    "missing_attribution",
    "empty_explanation",
    "contradictory_severity",
    "confidence_without_evidence",
    "circular_reasoning",
    "recommendation_absent",
]


class ReasoningCollapseDetector:
    """Detect structural failures in system reasoning output.

    A reasoning collapse is not a wrong answer — it is a broken output:
    missing fields, self-contradictory claims, or confidence without evidence.
    """

    def __init__(self) -> None:
        self._events: list[CollapseEvent] = []

    def check(self, incident_id: str, response: dict[str, Any]) -> list[CollapseEvent]:
        new_events: list[CollapseEvent] = []

        # Missing attribution with high confidence
        confidence = float(response.get("confidence", 0.0))
        attribution = response.get("attribution") or response.get("root_cause")
        if confidence > 0.70 and attribution is None:
            new_events.append(
                CollapseEvent(
                    collapse_type="confidence_without_evidence",
                    severity="high",
                    incident_id=incident_id,
                    description=f"confidence={confidence:.2f} but no attribution provided",
                    evidence={"confidence": confidence, "attribution": None},
                )
            )

        # Empty or missing explanation
        explanation = response.get("explanation") or response.get("reasoning") or ""
        if len(str(explanation).strip()) < 10 and confidence > 0.50:
            new_events.append(
                CollapseEvent(
                    collapse_type="empty_explanation",
                    severity="medium",
                    incident_id=incident_id,
                    description="Explanation is absent or too short to be meaningful",
                    evidence={
                        "explanation_length": len(str(explanation).strip()),
                        "confidence": confidence,
                    },
                )
            )

        # Contradictory severity
        severity_label = str(response.get("severity", "")).lower()
        metrics = response.get("metrics", {})
        error_rate = float(metrics.get("error_rate", -1.0))
        if severity_label == "low" and error_rate > 0.80:
            new_events.append(
                CollapseEvent(
                    collapse_type="contradictory_severity",
                    severity="high",
                    incident_id=incident_id,
                    description=f"severity=low but error_rate={error_rate:.2f}",
                    evidence={"severity": severity_label, "error_rate": error_rate},
                )
            )

        # Circular reasoning — attribution == symptom
        symptom = str(response.get("symptom", "")).lower().strip()
        root_cause = str(attribution or "").lower().strip()
        if symptom and root_cause and symptom == root_cause and len(symptom) > 3:
            new_events.append(
                CollapseEvent(
                    collapse_type="circular_reasoning",
                    severity="medium",
                    incident_id=incident_id,
                    description=f"attribution == symptom == '{symptom}'",
                    evidence={"symptom": symptom, "root_cause": root_cause},
                )
            )

        self._events.extend(new_events)
        return new_events

    def collapse_rate(self, window: int = 100) -> float:
        recent = self._events[-window:]
        if not recent:
            return 0.0
        unique_incidents = {e.incident_id for e in recent}
        return round(len(recent) / max(len(unique_incidents), 1), 4)

    def summary(self) -> dict[str, Any]:
        by_type: dict[str, int] = {}
        for e in self._events:
            by_type[e.collapse_type] = by_type.get(e.collapse_type, 0) + 1
        return {
            "total_collapse_events": len(self._events),
            "by_type": by_type,
            "collapse_rate_last_100": self.collapse_rate(100),
            "recent_events": [e.to_dict() for e in self._events[-5:]],
        }

    def prometheus_metrics(self) -> str:
        summary = self.summary()
        lines = [f"sentinelops_reasoning_collapse_total {summary['total_collapse_events']}"]
        for ctype, count in summary["by_type"].items():
            lines.append(f'sentinelops_reasoning_collapse_by_type{{type="{ctype}"}} {count}')
        return "\n".join(lines) + "\n"
