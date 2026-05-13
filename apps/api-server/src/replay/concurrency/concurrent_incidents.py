"""
Concurrent incident simulation for Phase 48 operational chaos.

Real production environments have multiple incidents running simultaneously.
This module merges independent incident event streams into a single interleaved
stream that a timeline reconstructor must disentangle.

Key properties:
  - Each incident retains its own incident_id label
  - Events are re-sorted by timestamp after merge (realistic receipt ordering)
  - Overlap window tracks which incidents were active at any point in time
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any


@dataclass
class OverlapWindow:
    """Describes a time window where multiple incidents were simultaneously active."""

    start_iso: str
    end_iso: str
    incident_ids: list[str]
    overlap_count: int

    @property
    def is_overlapping(self) -> bool:
        return self.overlap_count > 1


@dataclass
class ConcurrentSimulationResult:
    """Output of merging multiple concurrent incident streams."""

    merged_events: list[dict[str, Any]]
    incident_count: int
    total_events: int
    overlap_windows: list[OverlapWindow]
    incident_ids: list[str]

    @property
    def has_overlap(self) -> bool:
        return any(w.is_overlapping for w in self.overlap_windows)


class ConcurrentIncidentSimulator:
    """
    Merges multiple independent incident event streams into one interleaved stream.

    Usage:
        sim = ConcurrentIncidentSimulator()
        sim.add_incident("INC-001", events_a)
        sim.add_incident("INC-002", events_b)
        result = sim.simulate()
    """

    def __init__(self) -> None:
        self._incidents: dict[str, list[dict[str, Any]]] = {}

    def add_incident(
        self,
        incident_id: str,
        events: list[dict[str, Any]],
    ) -> None:
        """Register an incident event stream."""
        tagged = []
        for ev in events:
            ev_copy = copy.deepcopy(ev)
            ev_copy["incident_id"] = incident_id
            ev_copy.setdefault("labels", {})["concurrent_incident_id"] = incident_id
            tagged.append(ev_copy)
        self._incidents[incident_id] = tagged

    def simulate(self) -> ConcurrentSimulationResult:
        """Merge all registered incidents into one interleaved event stream."""
        all_events: list[dict[str, Any]] = []
        for evs in self._incidents.values():
            all_events.extend(evs)

        all_events.sort(key=lambda e: e.get("timestamp_iso", ""))

        overlap_windows = self._compute_overlap_windows()

        return ConcurrentSimulationResult(
            merged_events=all_events,
            incident_count=len(self._incidents),
            total_events=len(all_events),
            overlap_windows=overlap_windows,
            incident_ids=list(self._incidents.keys()),
        )

    def clear(self) -> None:
        self._incidents.clear()

    def _compute_overlap_windows(self) -> list[OverlapWindow]:
        """
        Build overlap windows from incident time spans.

        Computes the start/end timestamp of each incident, then finds
        intervals where more than one incident is active.
        """
        spans: dict[str, tuple[str, str]] = {}
        for inc_id, evs in self._incidents.items():
            if not evs:
                continue
            timestamps = sorted(e.get("timestamp_iso", "") for e in evs if e.get("timestamp_iso"))
            if timestamps:
                spans[inc_id] = (timestamps[0], timestamps[-1])

        if len(spans) < 2:
            return []

        # Find global overlap window (naive: any incident whose span intersects any other)
        windows: list[OverlapWindow] = []
        ids = list(spans.keys())
        for i, id_a in enumerate(ids):
            for id_b in ids[i + 1 :]:
                start_a, end_a = spans[id_a]
                start_b, end_b = spans[id_b]
                # Overlap exists if one starts before the other ends
                if start_a <= end_b and start_b <= end_a:
                    overlap_start = max(start_a, start_b)
                    overlap_end = min(end_a, end_b)
                    windows.append(
                        OverlapWindow(
                            start_iso=overlap_start,
                            end_iso=overlap_end,
                            incident_ids=[id_a, id_b],
                            overlap_count=2,
                        )
                    )
        return windows
