"""
Overlap resolution for concurrent incident streams.

When multiple incidents share the same infrastructure, their telemetry
overlaps in time. The OverlapResolver separates events that are unique
to one incident from those that appear in the shared overlap window.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ResolvedStream:
    """A partitioned view of a concurrent incident event stream."""

    incident_id: str
    owned_events: list[dict[str, Any]]  # events only from this incident
    overlap_events: list[dict[str, Any]]  # events in the shared time window
    noise_events: list[dict[str, Any]]  # noise deployments (no incident_id match)

    @property
    def total_events(self) -> int:
        return len(self.owned_events) + len(self.overlap_events) + len(self.noise_events)

    @property
    def overlap_fraction(self) -> float:
        total = self.total_events
        if total == 0:
            return 0.0
        return round(len(self.overlap_events) / total, 4)


@dataclass
class OverlapResolutionResult:
    streams: list[ResolvedStream]
    shared_overlap_window: tuple[str, str] | None  # (start_iso, end_iso)
    ambiguous_events: list[dict[str, Any]]  # events that cannot be assigned

    @property
    def has_ambiguity(self) -> bool:
        return len(self.ambiguous_events) > 0


class OverlapResolver:
    """
    Partitions a merged concurrent event stream back into per-incident views.

    Events are assigned by incident_id label. Events with no incident_id
    label or whose incident_id doesn't match any known incident are placed
    in the ambiguous bucket.
    """

    def resolve(
        self,
        merged_events: list[dict[str, Any]],
        known_incident_ids: list[str],
        overlap_window: tuple[str, str] | None = None,
    ) -> OverlapResolutionResult:
        """
        Partition merged events by incident_id.

        overlap_window: (start_iso, end_iso) describing the shared time range.
        Events within this window for a given incident are tagged as overlap_events.
        """
        per_incident: dict[str, list[dict[str, Any]]] = {iid: [] for iid in known_incident_ids}
        ambiguous: list[dict[str, Any]] = []

        for ev in merged_events:
            iid = ev.get("incident_id") or ev.get("labels", {}).get("concurrent_incident_id")
            if iid in per_incident:
                per_incident[iid].append(ev)
            else:
                ambiguous.append(ev)

        streams: list[ResolvedStream] = []
        for iid, evs in per_incident.items():
            owned: list[dict[str, Any]] = []
            overlap: list[dict[str, Any]] = []
            for ev in evs:
                ts = ev.get("timestamp_iso", "")
                if overlap_window and overlap_window[0] <= ts <= overlap_window[1]:
                    overlap.append(ev)
                else:
                    owned.append(ev)
            streams.append(
                ResolvedStream(
                    incident_id=iid,
                    owned_events=owned,
                    overlap_events=overlap,
                    noise_events=[e for e in ambiguous if e.get("_noise_deployment")],
                )
            )

        return OverlapResolutionResult(
            streams=streams,
            shared_overlap_window=overlap_window,
            ambiguous_events=[e for e in ambiguous if not e.get("_noise_deployment")],
        )
