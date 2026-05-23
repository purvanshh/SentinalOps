"""
Telemetry integrity checking for Phase 48 operational realism.

Detects:
  - Out-of-order timestamps relative to sequence numbers
  - Contradictory severity (same event_id with different severity)
  - Payload completeness below threshold
  - Clock skew signatures (cross-service timestamp inconsistencies)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class IntegrityViolation:
    violation_type: str
    event_id: str
    description: str
    impact: str  # "low" | "medium" | "high"


@dataclass
class IntegrityReport:
    violations: list[IntegrityViolation]
    total_events: int
    integrity_score: float  # 1.0 = fully intact, 0.0 = heavily corrupted
    clock_skew_detected: bool
    contradictions_found: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_events": self.total_events,
            "integrity_score": round(self.integrity_score, 4),
            "clock_skew_detected": self.clock_skew_detected,
            "contradictions_found": self.contradictions_found,
            "violation_count": len(self.violations),
            "violations": [
                {
                    "type": v.violation_type,
                    "event_id": v.event_id,
                    "description": v.description,
                    "impact": v.impact,
                }
                for v in self.violations
            ],
        }


def _parse_ts(ts: str) -> float | None:
    if not ts:
        return None
    try:
        from datetime import datetime

        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except (ValueError, AttributeError):
        return None


class TelemetryIntegrityChecker:
    """Validates internal consistency of a telemetry event stream."""

    _CLOCK_SKEW_THRESHOLD_S = 60.0  # >60s cross-service skew = suspicious
    _MAX_PAYLOAD_EMPTY_RATE = 0.30  # >30% empty payloads = degraded integrity

    def check(self, events: list[dict[str, Any]]) -> IntegrityReport:
        violations: list[IntegrityViolation] = []
        n = len(events)

        if n == 0:
            return IntegrityReport(
                violations=[],
                total_events=0,
                integrity_score=0.0,
                clock_skew_detected=False,
                contradictions_found=False,
            )

        # 1. Out-of-order timestamps relative to sequence_number
        seq_sorted = sorted(
            [ev for ev in events if ev.get("sequence_number") is not None],
            key=lambda e: e.get("sequence_number", 0),
        )
        for i in range(1, len(seq_sorted)):
            t_prev = _parse_ts(seq_sorted[i - 1].get("timestamp_iso", ""))
            t_curr = _parse_ts(seq_sorted[i].get("timestamp_iso", ""))
            if t_prev is not None and t_curr is not None and t_curr < t_prev:
                violations.append(
                    IntegrityViolation(
                        violation_type="out_of_order_timestamp",
                        event_id=seq_sorted[i].get("event_id", "unknown"),
                        description=(
                            f"Timestamp regresses between seq "
                            f"{seq_sorted[i - 1].get('sequence_number')} → "
                            f"{seq_sorted[i].get('sequence_number')}"
                        ),
                        impact="medium",
                    )
                )

        # 2. Contradictory severity (same event_id, different severity)
        by_id: dict[str, list[str]] = {}
        for ev in events:
            eid = ev.get("event_id", "")
            sev = ev.get("severity", "")
            if eid:
                by_id.setdefault(eid, []).append(sev)
        contradictions_found = False
        for eid, sevs in by_id.items():
            if len(set(sevs)) > 1:
                contradictions_found = True
                violations.append(
                    IntegrityViolation(
                        violation_type="severity_contradiction",
                        event_id=eid,
                        description=f"Same event_id has conflicting severities: {set(sevs)}",
                        impact="high",
                    )
                )

        # 3. Empty payload rate
        empty_payloads = sum(1 for ev in events if not ev.get("payload") or ev.get("payload") == {})
        empty_rate = empty_payloads / n
        if empty_rate > self._MAX_PAYLOAD_EMPTY_RATE:
            violations.append(
                IntegrityViolation(
                    violation_type="high_empty_payload_rate",
                    event_id="",
                    description=f"{empty_rate:.0%} of events have empty payloads",
                    impact="medium",
                )
            )

        # 4. Clock skew detection (cross-service timestamp spread)
        clock_skew_detected = self._detect_clock_skew(events)
        if clock_skew_detected:
            violations.append(
                IntegrityViolation(
                    violation_type="clock_skew_detected",
                    event_id="",
                    description="Cross-service timestamps diverge beyond expected bounds",
                    impact="medium",
                )
            )

        # Integrity score: starts at 1.0, penalised per violation impact
        _IMPACT_PENALTY = {"low": 0.05, "medium": 0.10, "high": 0.20}
        penalty = sum(_IMPACT_PENALTY.get(v.impact, 0.05) for v in violations)
        integrity_score = max(0.0, 1.0 - penalty)

        return IntegrityReport(
            violations=violations,
            total_events=n,
            integrity_score=round(integrity_score, 4),
            clock_skew_detected=clock_skew_detected,
            contradictions_found=contradictions_found,
        )

    def _detect_clock_skew(self, events: list[dict[str, Any]]) -> bool:
        """Check if different services have timestamps that diverge suspiciously."""
        service_last_ts: dict[str, float] = {}
        for ev in events:
            svc = ev.get("service", "")
            ts = _parse_ts(ev.get("timestamp_iso", ""))
            if svc and ts is not None:
                service_last_ts[svc] = ts

        if len(service_last_ts) < 2:
            return False

        ts_values = list(service_last_ts.values())
        spread = max(ts_values) - min(ts_values)
        return spread > self._CLOCK_SKEW_THRESHOLD_S
