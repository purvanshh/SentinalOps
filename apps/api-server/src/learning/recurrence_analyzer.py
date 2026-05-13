"""
Failure Recurrence Analyzer for SentinelOps Phase 46.

Detects recurring failure patterns by tracking incident fingerprints
across time. A "recurrence" is when the same mechanism+category
combination appears multiple times within a rolling window.

Tracked per pattern:
  - mechanism_id + incident_category fingerprint
  - occurrence count within rolling window
  - first and last seen timestamps (ISO)
  - mean time between recurrences (MTBR)
  - whether the pattern is escalating in frequency

Recurrence detection informs:
  - Escalation recommendations (recurring unresolved patterns)
  - Operator alerts ("this failure type has occurred N times in 7 days")
  - Long-term remediation effectiveness signals
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class IncidentFingerprint:
    """Minimal fingerprint used to detect recurrence."""

    incident_id: str
    mechanism_id: str | None
    incident_category: str
    timestamp_iso: str
    resolved: bool = False
    remediation_class: str | None = None


@dataclass
class RecurrencePattern:
    """A detected recurring failure pattern."""

    pattern_key: str  # "{mechanism_id}:{incident_category}"
    mechanism_id: str | None
    incident_category: str
    occurrence_count: int
    first_seen_iso: str
    last_seen_iso: str
    incident_ids: list[str]
    mean_time_between_recurrences_hours: float | None
    escalating: bool
    unresolved_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_key": self.pattern_key,
            "mechanism_id": self.mechanism_id,
            "incident_category": self.incident_category,
            "occurrence_count": self.occurrence_count,
            "first_seen_iso": self.first_seen_iso,
            "last_seen_iso": self.last_seen_iso,
            "incident_ids": self.incident_ids,
            "mean_time_between_recurrences_hours": (
                round(self.mean_time_between_recurrences_hours, 2)
                if self.mean_time_between_recurrences_hours is not None
                else None
            ),
            "escalating": self.escalating,
            "unresolved_count": self.unresolved_count,
        }


class FailureRecurrenceAnalyzer:
    """
    Detects and tracks recurring failure patterns.

    A pattern recurs when the same mechanism+category fingerprint
    appears at least `min_recurrence_count` times.
    """

    def __init__(self, min_recurrence_count: int = 2) -> None:
        self._min_recurrence = min_recurrence_count
        # pattern_key → list of fingerprints
        self._patterns: dict[str, list[IncidentFingerprint]] = {}

    def record_incident(self, fingerprint: IncidentFingerprint) -> None:
        """Record a new incident fingerprint."""
        key = self._make_key(fingerprint.mechanism_id, fingerprint.incident_category)
        self._patterns.setdefault(key, []).append(fingerprint)

    def mark_resolved(self, incident_id: str) -> bool:
        """Mark an incident as resolved. Returns True if the incident was found."""
        for fps in self._patterns.values():
            for fp in fps:
                if fp.incident_id == incident_id:
                    fp.resolved = True
                    return True
        return False

    def recurring_patterns(self) -> list[RecurrencePattern]:
        """Return all patterns with at least min_recurrence_count occurrences."""
        results = []
        for key, fps in self._patterns.items():
            if len(fps) >= self._min_recurrence:
                results.append(self._build_pattern(key, fps))
        return sorted(results, key=lambda p: p.occurrence_count, reverse=True)

    def pattern_for_mechanism(
        self, mechanism_id: str, incident_category: str
    ) -> RecurrencePattern | None:
        """Look up a specific pattern by mechanism and category."""
        key = self._make_key(mechanism_id, incident_category)
        fps = self._patterns.get(key)
        if not fps:
            return None
        return self._build_pattern(key, fps)

    def is_recurring(self, mechanism_id: str | None, incident_category: str) -> bool:
        """Return True if this mechanism+category combination is a known recurring pattern."""
        key = self._make_key(mechanism_id, incident_category)
        fps = self._patterns.get(key, [])
        return len(fps) >= self._min_recurrence

    def most_frequent_patterns(self, top_n: int = 5) -> list[RecurrencePattern]:
        return self.recurring_patterns()[:top_n]

    def total_unique_patterns(self) -> int:
        return len(self._patterns)

    def total_incidents_tracked(self) -> int:
        return sum(len(fps) for fps in self._patterns.values())

    def unresolved_recurring_patterns(self) -> list[RecurrencePattern]:
        """Return recurring patterns that have at least one unresolved incident."""
        return [p for p in self.recurring_patterns() if p.unresolved_count > 0]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_key(mechanism_id: str | None, incident_category: str) -> str:
        mech = mechanism_id or "unknown"
        return f"{mech}:{incident_category}"

    def _build_pattern(
        self, key: str, fps: list[IncidentFingerprint]
    ) -> RecurrencePattern:
        timestamps = [fp.timestamp_iso for fp in fps if fp.timestamp_iso]
        sorted_ts = sorted(timestamps)
        first = sorted_ts[0] if sorted_ts else ""
        last = sorted_ts[-1] if sorted_ts else ""

        mtbr = self._mean_time_between(sorted_ts)
        escalating = self._is_escalating(sorted_ts)

        unresolved = sum(1 for fp in fps if not fp.resolved)
        fp0 = fps[0]

        return RecurrencePattern(
            pattern_key=key,
            mechanism_id=fp0.mechanism_id,
            incident_category=fp0.incident_category,
            occurrence_count=len(fps),
            first_seen_iso=first,
            last_seen_iso=last,
            incident_ids=[fp.incident_id for fp in fps],
            mean_time_between_recurrences_hours=mtbr,
            escalating=escalating,
            unresolved_count=unresolved,
        )

    @staticmethod
    def _mean_time_between(sorted_iso: list[str]) -> float | None:
        """Compute mean time between consecutive timestamps in hours."""
        if len(sorted_iso) < 2:
            return None
        from datetime import datetime

        gaps_hours = []
        for i in range(1, len(sorted_iso)):
            try:
                t0 = datetime.fromisoformat(
                    sorted_iso[i - 1].replace("Z", "+00:00")
                )
                t1 = datetime.fromisoformat(sorted_iso[i].replace("Z", "+00:00"))
                gap = (t1 - t0).total_seconds() / 3600.0
                if gap >= 0:
                    gaps_hours.append(gap)
            except ValueError:
                continue
        if not gaps_hours:
            return None
        return round(sum(gaps_hours) / len(gaps_hours), 2)

    @staticmethod
    def _is_escalating(sorted_iso: list[str]) -> bool:
        """
        Return True if the time between incidents is shrinking (accelerating recurrence).

        Requires at least 3 occurrences to detect trend.
        """
        if len(sorted_iso) < 3:
            return False
        from datetime import datetime

        gaps = []
        for i in range(1, len(sorted_iso)):
            try:
                t0 = datetime.fromisoformat(sorted_iso[i - 1].replace("Z", "+00:00"))
                t1 = datetime.fromisoformat(sorted_iso[i].replace("Z", "+00:00"))
                gaps.append((t1 - t0).total_seconds())
            except ValueError:
                continue
        if len(gaps) < 2:
            return False
        # Escalating if the last gap is less than the first gap
        return gaps[-1] < gaps[0]
