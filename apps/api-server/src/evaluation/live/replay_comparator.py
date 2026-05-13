"""
Replay comparator for SentinelOps Phase 47.

Side-by-side comparison of two replay sessions, identifying
differences in event coverage, timeline reconstruction, and
incident handling across sessions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class SessionProfile:
    """Summarized profile of one replay session."""

    session_hash: str
    total_events: int
    incident_count: int
    mean_completeness: float
    severity_distribution: dict[str, int]
    service_set: set[str]
    kind_distribution: dict[str, int]
    mean_event_count_per_incident: float

    def coverage_score(self) -> float:
        """0–1 score: fraction of expected kinds present at adequate levels."""
        expected = {"metric", "log", "alert"}
        present = {k for k, v in self.kind_distribution.items() if v > 0} & expected
        return len(present) / len(expected)


@dataclass
class SessionDiff:
    """Differences between two replay sessions."""

    session_a_hash: str
    session_b_hash: str
    event_count_delta: int
    incident_count_delta: int
    completeness_delta: float
    coverage_score_delta: float
    services_only_in_a: set[str]
    services_only_in_b: set[str]
    shared_services: set[str]
    severity_deltas: dict[str, int]
    verdict: str  # "equivalent", "a_richer", "b_richer", "divergent"

    def is_equivalent(self) -> bool:
        return self.verdict == "equivalent"

    def summary(self) -> str:
        return (
            f"verdict={self.verdict} "
            f"events_delta={self.event_count_delta:+d} "
            f"completeness_delta={self.completeness_delta:+.3f}"
        )


class ReplayComparator:
    """
    Compares two replay sessions or event lists.

    Produces a SessionDiff that quantifies coverage, completeness,
    and service intersection differences between sessions.
    """

    _EQUIVALENCE_THRESHOLD: float = 0.05

    def compare_sessions(
        self,
        session_a: SessionProfile,
        session_b: SessionProfile,
    ) -> SessionDiff:
        event_delta = session_b.total_events - session_a.total_events
        incident_delta = session_b.incident_count - session_a.incident_count
        completeness_delta = session_b.mean_completeness - session_a.mean_completeness
        coverage_delta = session_b.coverage_score() - session_a.coverage_score()

        services_a = session_a.service_set
        services_b = session_b.service_set
        only_a = services_a - services_b
        only_b = services_b - services_a
        shared = services_a & services_b

        severity_deltas: dict[str, int] = {}
        all_severities = set(session_a.severity_distribution) | set(session_b.severity_distribution)
        for sev in all_severities:
            severity_deltas[sev] = session_b.severity_distribution.get(
                sev, 0
            ) - session_a.severity_distribution.get(sev, 0)

        verdict = self._verdict(
            completeness_delta=completeness_delta,
            event_delta=event_delta,
            only_a=only_a,
            only_b=only_b,
        )

        return SessionDiff(
            session_a_hash=session_a.session_hash,
            session_b_hash=session_b.session_hash,
            event_count_delta=event_delta,
            incident_count_delta=incident_delta,
            completeness_delta=completeness_delta,
            coverage_score_delta=coverage_delta,
            services_only_in_a=only_a,
            services_only_in_b=only_b,
            shared_services=shared,
            severity_deltas=severity_deltas,
            verdict=verdict,
        )

    def compare_event_lists(
        self,
        events_a: list[dict[str, Any]],
        events_b: list[dict[str, Any]],
        session_hash_a: str = "session_a",
        session_hash_b: str = "session_b",
    ) -> SessionDiff:
        profile_a = self.profile_events(events_a, session_hash=session_hash_a)
        profile_b = self.profile_events(events_b, session_hash=session_hash_b)
        return self.compare_sessions(profile_a, profile_b)

    def profile_events(
        self,
        events: list[dict[str, Any]],
        session_hash: str = "",
    ) -> SessionProfile:
        if not events:
            return SessionProfile(
                session_hash=session_hash,
                total_events=0,
                incident_count=0,
                mean_completeness=0.0,
                severity_distribution={},
                service_set=set(),
                kind_distribution={},
                mean_event_count_per_incident=0.0,
            )

        severity_dist: dict[str, int] = {}
        kind_dist: dict[str, int] = {}
        services: set[str] = set()
        incidents: set[str] = set()

        for ev in events:
            sev = ev.get("severity", "info")
            severity_dist[sev] = severity_dist.get(sev, 0) + 1
            kind = ev.get("kind", "unknown").lower()
            kind_dist[kind] = kind_dist.get(kind, 0) + 1
            svc = ev.get("service", "")
            if svc:
                services.add(svc)
            iid = ev.get("incident_id")
            if iid:
                incidents.add(str(iid))

        completeness = self._compute_completeness(kind_dist)
        incident_count = len(incidents) if incidents else 1
        mean_per_incident = len(events) / incident_count

        return SessionProfile(
            session_hash=session_hash,
            total_events=len(events),
            incident_count=incident_count,
            mean_completeness=completeness,
            severity_distribution=severity_dist,
            service_set=services,
            kind_distribution=kind_dist,
            mean_event_count_per_incident=mean_per_incident,
        )

    # ------------------------------------------------------------------

    def _compute_completeness(self, kind_dist: dict[str, int]) -> float:
        expected = {"metric", "log", "alert"}
        present = {k for k in kind_dist if k in expected and kind_dist[k] > 0}
        return len(present) / len(expected)

    def _verdict(
        self,
        completeness_delta: float,
        event_delta: int,
        only_a: set[str],
        only_b: set[str],
    ) -> str:
        threshold = self._EQUIVALENCE_THRESHOLD
        if abs(completeness_delta) <= threshold and len(only_a) == 0 and len(only_b) == 0:
            return "equivalent"
        if completeness_delta < -threshold or (only_a and not only_b):
            return "a_richer"
        if completeness_delta > threshold or (only_b and not only_a):
            return "b_richer"
        return "divergent"
