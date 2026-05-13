"""
Telemetry completeness analysis for Phase 48 operational realism.

Measures how complete the telemetry picture is for an incident.
A score of 1.0 means all expected signal kinds are present with
well-formed timestamps and consistent severity progression.
A score near 0.0 means the telemetry is sparse, contradictory, or missing
critical signal types needed to diagnose the incident.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_EXPECTED_KINDS = {"metric", "log", "alert"}
_EXPECTED_SEVERITIES = {"warning", "error", "critical"}

# Weights for completeness scoring components
_W_KIND = 0.40
_W_SEVERITY = 0.20
_W_TIMESTAMP = 0.25
_W_SERVICE = 0.15


@dataclass
class CompletenessScore:
    """Decomposed completeness score for a single incident's telemetry."""

    kind_coverage: float  # fraction of expected kinds present
    severity_coverage: float  # fraction of expected severity levels observed
    timestamp_validity: float  # fraction of events with parseable timestamps
    service_coverage: float  # fraction of events with non-empty service fields
    overall: float  # weighted composite

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind_coverage": round(self.kind_coverage, 4),
            "severity_coverage": round(self.severity_coverage, 4),
            "timestamp_validity": round(self.timestamp_validity, 4),
            "service_coverage": round(self.service_coverage, 4),
            "overall": round(self.overall, 4),
        }


def _is_valid_timestamp(ts: str) -> bool:
    if not ts:
        return False
    try:
        from datetime import datetime

        datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return True
    except (ValueError, AttributeError):
        return False


class CompletenessAnalyzer:
    """
    Scores the telemetry completeness of an incident event set.

    Works on raw event dicts — no TelemetryEvent objects required.
    """

    def analyze(self, events: list[dict[str, Any]]) -> CompletenessScore:
        if not events:
            return CompletenessScore(
                kind_coverage=0.0,
                severity_coverage=0.0,
                timestamp_validity=0.0,
                service_coverage=0.0,
                overall=0.0,
            )

        n = len(events)

        # Kind coverage
        present_kinds = {ev.get("kind", "") for ev in events}
        kind_coverage = len(present_kinds & _EXPECTED_KINDS) / len(_EXPECTED_KINDS)

        # Severity coverage
        present_severities = {ev.get("severity", "").lower() for ev in events}
        severity_coverage = len(present_severities & _EXPECTED_SEVERITIES) / len(
            _EXPECTED_SEVERITIES
        )

        # Timestamp validity
        valid_ts = sum(1 for ev in events if _is_valid_timestamp(ev.get("timestamp_iso", "")))
        timestamp_validity = valid_ts / n

        # Service coverage
        with_service = sum(1 for ev in events if ev.get("service", "").strip())
        service_coverage = with_service / n

        overall = (
            _W_KIND * kind_coverage
            + _W_SEVERITY * severity_coverage
            + _W_TIMESTAMP * timestamp_validity
            + _W_SERVICE * service_coverage
        )

        return CompletenessScore(
            kind_coverage=kind_coverage,
            severity_coverage=severity_coverage,
            timestamp_validity=timestamp_validity,
            service_coverage=service_coverage,
            overall=round(overall, 4),
        )
