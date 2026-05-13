"""
Timeline Reconstructor for SentinelOps Phase 47.

Builds ordered incident timelines from raw TelemetryEvent streams.
Produces:
  - ordered event timelines per incident
  - critical transition points
  - operator intervention sequences
  - causal chains (propagation sequences)

Telemetry completeness is scored as the fraction of expected event
kinds that are present in the incident's event set.

Design constraints:
  - All outputs are deterministic given the same input stream.
  - No external services or I/O required.
  - Partial telemetry is handled gracefully (completeness < 1.0).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from replay.replay_models import EventKind, IncidentTimeline, TelemetryEvent

_EXPECTED_KINDS: set[EventKind] = {
    EventKind.METRIC,
    EventKind.LOG,
    EventKind.ALERT,
}

_CRITICAL_SEVERITIES = {"critical", "error", "fatal"}

_OPERATOR_KINDS = {EventKind.OPERATOR_ACTION, EventKind.REMEDIATION_ACTION}

_CAUSAL_KINDS = {
    EventKind.ALERT,
    EventKind.DEPLOYMENT,
    EventKind.TOPOLOGY_CHANGE,
    EventKind.REMEDIATION_ACTION,
}


def _parse_ts(ts: str) -> datetime:
    """Parse ISO timestamp; fall back to epoch on failure."""
    if not ts:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)


def _duration_seconds(start: str, end: str) -> float:
    t0 = _parse_ts(start)
    t1 = _parse_ts(end)
    delta = (t1 - t0).total_seconds()
    return max(0.0, delta)


def _completeness(events: list[TelemetryEvent]) -> float:
    """Fraction of expected event kinds present in the set."""
    present = {ev.kind for ev in events}
    covered = len(present & _EXPECTED_KINDS)
    return round(covered / len(_EXPECTED_KINDS), 4)


def reconstruct_incident(
    incident_id: str,
    events: list[TelemetryEvent],
) -> IncidentTimeline:
    """
    Build an IncidentTimeline from a list of events for one incident.

    Events need not be pre-sorted; this function sorts them.
    """
    sorted_events = sorted(
        events,
        key=lambda e: (e.timestamp_iso, e.sequence_number, e.event_id),
    )

    if not sorted_events:
        return IncidentTimeline(
            incident_id=incident_id,
            timeline=[],
            critical_transitions=[],
            operator_interventions=[],
            causal_chain=[],
            start_timestamp_iso="",
            end_timestamp_iso="",
            duration_seconds=0.0,
            telemetry_completeness=0.0,
            event_count=0,
        )

    start_ts = sorted_events[0].timestamp_iso
    end_ts = sorted_events[-1].timestamp_iso

    timeline: list[dict[str, Any]] = [ev.to_dict() for ev in sorted_events]

    critical_transitions: list[dict[str, Any]] = []
    for ev in sorted_events:
        if ev.severity.lower() in _CRITICAL_SEVERITIES or ev.kind == EventKind.ALERT:
            critical_transitions.append(
                {
                    "timestamp_iso": ev.timestamp_iso,
                    "event_id": ev.event_id,
                    "kind": ev.kind.value,
                    "service": ev.service,
                    "severity": ev.severity,
                    "description": ev.payload.get("description", ev.payload.get("message", "")),
                }
            )

    operator_interventions: list[dict[str, Any]] = []
    for ev in sorted_events:
        if ev.kind in _OPERATOR_KINDS:
            operator_interventions.append(
                {
                    "timestamp_iso": ev.timestamp_iso,
                    "event_id": ev.event_id,
                    "kind": ev.kind.value,
                    "service": ev.service,
                    "operator_id": ev.labels.get("operator_id", ""),
                    "action": ev.payload.get("action", ""),
                    "note": ev.payload.get("note", ""),
                }
            )

    causal_chain: list[dict[str, Any]] = []
    for ev in sorted_events:
        if ev.kind in _CAUSAL_KINDS:
            causal_chain.append(
                {
                    "timestamp_iso": ev.timestamp_iso,
                    "event_id": ev.event_id,
                    "kind": ev.kind.value,
                    "service": ev.service,
                    "cause": ev.payload.get("cause", ""),
                    "effect": ev.payload.get("effect", ""),
                }
            )

    return IncidentTimeline(
        incident_id=incident_id,
        timeline=timeline,
        critical_transitions=critical_transitions,
        operator_interventions=operator_interventions,
        causal_chain=causal_chain,
        start_timestamp_iso=start_ts,
        end_timestamp_iso=end_ts,
        duration_seconds=_duration_seconds(start_ts, end_ts),
        telemetry_completeness=_completeness(sorted_events),
        event_count=len(sorted_events),
    )


def reconstruct_all(
    events: list[TelemetryEvent],
) -> dict[str, IncidentTimeline]:
    """
    Reconstruct timelines for all incidents found in an event stream.

    Events with no incident_id are grouped under "unknown".
    Returns a dict keyed by incident_id.
    """
    by_incident: dict[str, list[TelemetryEvent]] = {}
    for ev in events:
        key = ev.incident_id or "unknown"
        by_incident.setdefault(key, []).append(ev)

    return {
        incident_id: reconstruct_incident(incident_id, evs)
        for incident_id, evs in by_incident.items()
    }
