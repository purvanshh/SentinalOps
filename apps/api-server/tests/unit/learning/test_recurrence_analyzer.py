"""Tests for FailureRecurrenceAnalyzer (Phase 46)."""

from __future__ import annotations

import pytest
from learning.recurrence_analyzer import FailureRecurrenceAnalyzer, IncidentFingerprint


def _fp(
    incident_id: str,
    mechanism_id: str | None = "memory_pressure",
    category: str = "performance",
    ts: str = "2026-05-01T10:00:00Z",
    resolved: bool = False,
) -> IncidentFingerprint:
    return IncidentFingerprint(
        incident_id=incident_id,
        mechanism_id=mechanism_id,
        incident_category=category,
        timestamp_iso=ts,
        resolved=resolved,
    )


class TestFailureRecurrenceAnalyzer:
    def test_empty_produces_no_patterns(self):
        analyzer = FailureRecurrenceAnalyzer()
        assert analyzer.recurring_patterns() == []

    def test_single_incident_not_recurring(self):
        analyzer = FailureRecurrenceAnalyzer()
        analyzer.record_incident(_fp("INC-001"))
        assert not analyzer.is_recurring("memory_pressure", "performance")

    def test_two_incidents_triggers_recurrence(self):
        analyzer = FailureRecurrenceAnalyzer()
        analyzer.record_incident(_fp("INC-001"))
        analyzer.record_incident(_fp("INC-002"))
        assert analyzer.is_recurring("memory_pressure", "performance")

    def test_three_incidents_in_pattern(self):
        analyzer = FailureRecurrenceAnalyzer()
        for i in range(3):
            analyzer.record_incident(_fp(f"INC-{i:03d}"))
        patterns = analyzer.recurring_patterns()
        assert len(patterns) == 1
        assert patterns[0].occurrence_count == 3

    def test_different_mechanisms_separate_patterns(self):
        analyzer = FailureRecurrenceAnalyzer()
        for i in range(2):
            analyzer.record_incident(_fp(f"INC-A{i}", mechanism_id="memory_pressure"))
        for i in range(2):
            analyzer.record_incident(_fp(f"INC-B{i}", mechanism_id="retry_storm"))
        patterns = analyzer.recurring_patterns()
        assert len(patterns) == 2

    def test_mark_resolved(self):
        analyzer = FailureRecurrenceAnalyzer()
        analyzer.record_incident(_fp("INC-001"))
        analyzer.record_incident(_fp("INC-002"))
        result = analyzer.mark_resolved("INC-001")
        assert result is True
        pattern = analyzer.pattern_for_mechanism("memory_pressure", "performance")
        assert pattern is not None
        assert pattern.unresolved_count == 1

    def test_mark_resolved_unknown_returns_false(self):
        analyzer = FailureRecurrenceAnalyzer()
        assert analyzer.mark_resolved("UNKNOWN") is False

    def test_unresolved_recurring_patterns(self):
        analyzer = FailureRecurrenceAnalyzer()
        analyzer.record_incident(_fp("INC-001"))
        analyzer.record_incident(_fp("INC-002"))
        unresolved = analyzer.unresolved_recurring_patterns()
        assert len(unresolved) == 1

    def test_all_resolved_not_in_unresolved(self):
        analyzer = FailureRecurrenceAnalyzer()
        analyzer.record_incident(_fp("INC-001"))
        analyzer.record_incident(_fp("INC-002"))
        analyzer.mark_resolved("INC-001")
        analyzer.mark_resolved("INC-002")
        pattern = analyzer.pattern_for_mechanism("memory_pressure", "performance")
        assert pattern.unresolved_count == 0

    def test_total_incidents_tracked(self):
        analyzer = FailureRecurrenceAnalyzer()
        for i in range(5):
            analyzer.record_incident(_fp(f"INC-{i:03d}"))
        assert analyzer.total_incidents_tracked() == 5

    def test_total_unique_patterns(self):
        analyzer = FailureRecurrenceAnalyzer()
        analyzer.record_incident(_fp("INC-A", mechanism_id="memory_pressure"))
        analyzer.record_incident(_fp("INC-B", mechanism_id="retry_storm"))
        assert analyzer.total_unique_patterns() == 2

    def test_escalating_pattern_detected(self):
        analyzer = FailureRecurrenceAnalyzer()
        # Timestamps getting closer together = escalating
        analyzer.record_incident(_fp("INC-001", ts="2026-05-01T00:00:00Z"))
        analyzer.record_incident(_fp("INC-002", ts="2026-05-01T06:00:00Z"))
        analyzer.record_incident(_fp("INC-003", ts="2026-05-01T09:00:00Z"))
        pattern = analyzer.pattern_for_mechanism("memory_pressure", "performance")
        assert pattern is not None
        assert pattern.escalating is True

    def test_non_escalating_pattern(self):
        analyzer = FailureRecurrenceAnalyzer()
        # Timestamps getting further apart = not escalating
        analyzer.record_incident(_fp("INC-001", ts="2026-05-01T00:00:00Z"))
        analyzer.record_incident(_fp("INC-002", ts="2026-05-01T04:00:00Z"))
        analyzer.record_incident(_fp("INC-003", ts="2026-05-01T20:00:00Z"))
        pattern = analyzer.pattern_for_mechanism("memory_pressure", "performance")
        assert pattern is not None
        assert pattern.escalating is False

    def test_mean_time_between_computed(self):
        analyzer = FailureRecurrenceAnalyzer()
        analyzer.record_incident(_fp("INC-001", ts="2026-05-01T00:00:00Z"))
        analyzer.record_incident(_fp("INC-002", ts="2026-05-01T02:00:00Z"))
        pattern = analyzer.pattern_for_mechanism("memory_pressure", "performance")
        assert pattern.mean_time_between_recurrences_hours == pytest.approx(2.0, abs=0.1)

    def test_most_frequent_patterns_sorted(self):
        analyzer = FailureRecurrenceAnalyzer()
        for i in range(5):
            analyzer.record_incident(_fp(f"INC-A{i}", mechanism_id="memory_pressure"))
        for i in range(2):
            analyzer.record_incident(_fp(f"INC-B{i}", mechanism_id="retry_storm"))
        top = analyzer.most_frequent_patterns(top_n=2)
        assert top[0].occurrence_count >= top[1].occurrence_count

    def test_none_mechanism_uses_unknown_key(self):
        analyzer = FailureRecurrenceAnalyzer()
        analyzer.record_incident(_fp("INC-001", mechanism_id=None))
        analyzer.record_incident(_fp("INC-002", mechanism_id=None))
        assert analyzer.is_recurring(None, "performance")
