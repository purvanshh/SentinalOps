"""Tests for IncidentEvolutionTracker (Phase 46)."""

from __future__ import annotations

import pytest
from learning.incident_evolution import (
    IncidentEvolutionTracker,
    IncidentStage,
)


class TestIncidentEvolutionTracker:
    def test_start_incident_creates_trace(self):
        tracker = IncidentEvolutionTracker()
        trace = tracker.start_incident(
            "INC-001",
            ai_confidence=0.60,
            mechanism_id="memory_pressure",
            remediation_class=None,
            timestamp_iso="2026-05-01T10:00:00Z",
        )
        assert trace.incident_id == "INC-001"
        assert trace.current_stage == IncidentStage.DETECTED

    def test_advance_stage_appends_event(self):
        tracker = IncidentEvolutionTracker()
        tracker.start_incident(
            "INC-001",
            ai_confidence=0.60,
            mechanism_id="memory_pressure",
            remediation_class=None,
            timestamp_iso="2026-05-01T10:00:00Z",
        )
        tracker.advance_stage(
            "INC-001",
            stage=IncidentStage.INVESTIGATING,
            ai_confidence=0.70,
            mechanism_id="memory_pressure",
            remediation_class=None,
            timestamp_iso="2026-05-01T10:05:00Z",
        )
        trace = tracker.trace_for("INC-001")
        assert len(trace.events) == 2
        assert trace.current_stage == IncidentStage.INVESTIGATING

    def test_assessment_changed_flag_when_mechanism_changes(self):
        tracker = IncidentEvolutionTracker()
        tracker.start_incident(
            "INC-001",
            ai_confidence=0.60,
            mechanism_id="memory_pressure",
            remediation_class=None,
            timestamp_iso="2026-05-01T10:00:00Z",
        )
        ev = tracker.advance_stage(
            "INC-001",
            stage=IncidentStage.HYPOTHESIS_FORMED,
            ai_confidence=0.75,
            mechanism_id="retry_storm",  # changed!
            remediation_class="add_circuit_breaker",
            timestamp_iso="2026-05-01T10:10:00Z",
        )
        assert ev.assessment_changed is True

    def test_no_assessment_change_when_mechanism_stable(self):
        tracker = IncidentEvolutionTracker()
        tracker.start_incident(
            "INC-001",
            ai_confidence=0.60,
            mechanism_id="memory_pressure",
            remediation_class=None,
            timestamp_iso="2026-05-01T10:00:00Z",
        )
        ev = tracker.advance_stage(
            "INC-001",
            stage=IncidentStage.INVESTIGATING,
            ai_confidence=0.70,
            mechanism_id="memory_pressure",  # same
            remediation_class=None,
            timestamp_iso="2026-05-01T10:05:00Z",
        )
        assert ev.assessment_changed is False

    def test_assessment_was_revised_property(self):
        tracker = IncidentEvolutionTracker()
        tracker.start_incident(
            "INC-001",
            ai_confidence=0.60,
            mechanism_id="memory_pressure",
            remediation_class=None,
            timestamp_iso="2026-05-01T10:00:00Z",
        )
        tracker.advance_stage(
            "INC-001",
            stage=IncidentStage.HYPOTHESIS_FORMED,
            ai_confidence=0.75,
            mechanism_id="retry_storm",
            remediation_class=None,
            timestamp_iso="2026-05-01T10:10:00Z",
        )
        trace = tracker.trace_for("INC-001")
        assert trace.assessment_was_revised is True

    def test_revision_count(self):
        tracker = IncidentEvolutionTracker()
        tracker.start_incident(
            "INC-001",
            ai_confidence=0.60,
            mechanism_id="memory_pressure",
            remediation_class=None,
            timestamp_iso="2026-05-01T10:00:00Z",
        )
        tracker.advance_stage(
            "INC-001",
            stage=IncidentStage.INVESTIGATING,
            ai_confidence=0.65,
            mechanism_id="retry_storm",  # revision 1
            remediation_class=None,
            timestamp_iso="2026-05-01T10:05:00Z",
        )
        tracker.advance_stage(
            "INC-001",
            stage=IncidentStage.HYPOTHESIS_FORMED,
            ai_confidence=0.75,
            mechanism_id="memory_pressure",  # revision 2
            remediation_class=None,
            timestamp_iso="2026-05-01T10:10:00Z",
        )
        trace = tracker.trace_for("INC-001")
        assert trace.revision_count == 2

    def test_confidence_trajectory(self):
        tracker = IncidentEvolutionTracker()
        tracker.start_incident(
            "INC-001",
            ai_confidence=0.50,
            mechanism_id=None,
            remediation_class=None,
            timestamp_iso="2026-05-01T10:00:00Z",
        )
        tracker.advance_stage(
            "INC-001",
            stage=IncidentStage.INVESTIGATING,
            ai_confidence=0.65,
            mechanism_id=None,
            remediation_class=None,
            timestamp_iso="2026-05-01T10:05:00Z",
        )
        tracker.advance_stage(
            "INC-001",
            stage=IncidentStage.HYPOTHESIS_FORMED,
            ai_confidence=0.80,
            mechanism_id=None,
            remediation_class=None,
            timestamp_iso="2026-05-01T10:10:00Z",
        )
        trace = tracker.trace_for("INC-001")
        assert trace.confidence_trajectory == [0.50, 0.65, 0.80]

    def test_confidence_trend_increasing(self):
        tracker = IncidentEvolutionTracker()
        tracker.start_incident("INC-001", ai_confidence=0.40, mechanism_id=None, remediation_class=None, timestamp_iso="2026-05-01T10:00:00Z")  # noqa: E501
        tracker.advance_stage("INC-001", stage=IncidentStage.INVESTIGATING, ai_confidence=0.60, mechanism_id=None, remediation_class=None, timestamp_iso="2026-05-01T10:05:00Z")  # noqa: E501
        tracker.advance_stage("INC-001", stage=IncidentStage.HYPOTHESIS_FORMED, ai_confidence=0.80, mechanism_id=None, remediation_class=None, timestamp_iso="2026-05-01T10:10:00Z")  # noqa: E501
        trace = tracker.trace_for("INC-001")
        assert trace.confidence_trend == "increasing"

    def test_close_incident(self):
        tracker = IncidentEvolutionTracker()
        tracker.start_incident("INC-001", ai_confidence=0.70, mechanism_id="memory_pressure", remediation_class=None, timestamp_iso="2026-05-01T10:00:00Z")  # noqa: E501
        tracker.close_incident("INC-001", final_mechanism_id="memory_pressure", final_remediation_class="scale_replicas", final_confidence=0.90, timestamp_iso="2026-05-01T11:00:00Z")  # noqa: E501
        trace = tracker.trace_for("INC-001")
        assert trace.current_stage == IncidentStage.CLOSED

    def test_initial_mechanism_and_final_mechanism(self):
        tracker = IncidentEvolutionTracker()
        tracker.start_incident("INC-001", ai_confidence=0.60, mechanism_id="memory_pressure", remediation_class=None, timestamp_iso="2026-05-01T10:00:00Z")  # noqa: E501
        tracker.advance_stage("INC-001", stage=IncidentStage.HYPOTHESIS_FORMED, ai_confidence=0.75, mechanism_id="retry_storm", remediation_class=None, timestamp_iso="2026-05-01T10:10:00Z")  # noqa: E501
        trace = tracker.trace_for("INC-001")
        assert trace.initial_mechanism == "memory_pressure"
        assert trace.final_mechanism == "retry_storm"

    def test_traces_with_revisions(self):
        tracker = IncidentEvolutionTracker()
        tracker.start_incident("INC-001", ai_confidence=0.60, mechanism_id="memory_pressure", remediation_class=None, timestamp_iso="2026-05-01T10:00:00Z")  # noqa: E501
        tracker.advance_stage("INC-001", stage=IncidentStage.INVESTIGATING, ai_confidence=0.65, mechanism_id="retry_storm", remediation_class=None, timestamp_iso="2026-05-01T10:05:00Z")  # noqa: E501
        tracker.start_incident("INC-002", ai_confidence=0.70, mechanism_id="retry_storm", remediation_class=None, timestamp_iso="2026-05-01T11:00:00Z")  # noqa: E501
        tracker.advance_stage("INC-002", stage=IncidentStage.INVESTIGATING, ai_confidence=0.75, mechanism_id="retry_storm", remediation_class=None, timestamp_iso="2026-05-01T11:05:00Z")  # noqa: E501
        revised = tracker.traces_with_revisions()
        assert len(revised) == 1
        assert revised[0].incident_id == "INC-001"

    def test_mechanism_diagnosis_accuracy(self):
        tracker = IncidentEvolutionTracker()
        tracker.start_incident("INC-001", ai_confidence=0.70, mechanism_id="memory_pressure", remediation_class=None, timestamp_iso="2026-05-01T10:00:00Z")  # noqa: E501
        tracker.close_incident("INC-001", final_mechanism_id="memory_pressure", final_remediation_class=None, final_confidence=0.85, timestamp_iso="2026-05-01T11:00:00Z")  # noqa: E501
        tracker.start_incident("INC-002", ai_confidence=0.65, mechanism_id="memory_pressure", remediation_class=None, timestamp_iso="2026-05-01T12:00:00Z")  # noqa: E501
        tracker.close_incident("INC-002", final_mechanism_id="retry_storm", final_remediation_class=None, final_confidence=0.75, timestamp_iso="2026-05-01T13:00:00Z")  # noqa: E501
        accuracy = tracker.mechanism_diagnosis_accuracy()
        assert "memory_pressure" in accuracy
        mp = accuracy["memory_pressure"]
        assert mp["first_diagnosis_accuracy"] == pytest.approx(0.5, abs=0.01)

    def test_mean_revisions_per_incident(self):
        tracker = IncidentEvolutionTracker()
        tracker.start_incident("INC-001", ai_confidence=0.60, mechanism_id="A", remediation_class=None, timestamp_iso="2026-05-01T10:00:00Z")  # noqa: E501
        tracker.advance_stage("INC-001", stage=IncidentStage.INVESTIGATING, ai_confidence=0.65, mechanism_id="B", remediation_class=None, timestamp_iso="2026-05-01T10:05:00Z")  # noqa: E501
        tracker.start_incident("INC-002", ai_confidence=0.70, mechanism_id="A", remediation_class=None, timestamp_iso="2026-05-01T11:00:00Z")  # noqa: E501
        mean_revisions = tracker.mean_revisions_per_incident()
        assert mean_revisions == pytest.approx(0.5, abs=0.01)

    def test_unknown_incident_returns_none(self):
        tracker = IncidentEvolutionTracker()
        assert tracker.trace_for("UNKNOWN") is None

    def test_trace_to_dict(self):
        tracker = IncidentEvolutionTracker()
        tracker.start_incident("INC-001", ai_confidence=0.70, mechanism_id="memory_pressure", remediation_class=None, timestamp_iso="2026-05-01T10:00:00Z")  # noqa: E501
        trace = tracker.trace_for("INC-001")
        d = trace.to_dict()
        for key in [
            "incident_id", "events", "current_stage", "assessment_was_revised",
            "confidence_trajectory", "confidence_trend",
        ]:
            assert key in d
