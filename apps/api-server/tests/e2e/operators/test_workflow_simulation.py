from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

import pytest
from operators.workflow.decision_lifecycle import (
    DecisionEvent,
    DecisionLifecycleTracker,
    DecisionStage,
)
from operators.workflow.escalation_pathway import (
    EscalationChain,
    EscalationLevel,
)
from operators.workflow.operator_session import (
    SessionManager,
    SessionPhase,
)
from operators.workflow.workflow_simulator import WorkflowSimulator

# ---------------------------------------------------------------------------
# WorkflowSimulator
# ---------------------------------------------------------------------------


class TestWorkflowSimulator:
    def setup_method(self) -> None:
        self.sim = WorkflowSimulator()

    def test_empty_session_returns_zero_fatigue(self) -> None:
        state = self.sim.simulate_session([])
        assert state.fatigue_score == 0.0
        assert state.confidence_in_system == 1.0
        assert state.override_frequency == 0.0
        assert state.cognitive_load == 0.0

    def test_fatigue_accumulates_per_incident(self) -> None:
        # Use the same id for all incidents to eliminate context-switch penalties.
        incidents = [{"id": "inc-0", "resolved": True} for _ in range(4)]
        state = self.sim.simulate_session(incidents)
        expected_base = 4 * 0.05
        assert state.fatigue_score == pytest.approx(expected_base, abs=0.01)

    def test_unresolved_incident_adds_penalty(self) -> None:
        resolved = self.sim.simulate_session([{"id": "a", "resolved": True}])
        unresolved = self.sim.simulate_session([{"id": "a", "resolved": False}])
        assert unresolved.fatigue_score > resolved.fatigue_score

    def test_fatigue_capped_at_one(self) -> None:
        incidents = [{"id": f"inc-{i}", "resolved": False} for i in range(30)]
        state = self.sim.simulate_session(incidents)
        assert state.fatigue_score == 1.0

    def test_context_switch_adds_penalty(self) -> None:
        no_switch = self.sim.simulate_session(
            [
                {"id": "a", "resolved": True},
                {"id": "a", "resolved": True},
            ]
        )
        with_switch = self.sim.simulate_session(
            [
                {"id": "a", "resolved": True},
                {"id": "b", "resolved": True},
            ]
        )
        assert with_switch.fatigue_score > no_switch.fatigue_score

    def test_false_positive_degrades_confidence(self) -> None:
        state = self.sim.simulate_session(
            [
                {"id": "a", "false_positive": True, "resolved": True},
            ]
        )
        assert state.confidence_in_system == pytest.approx(0.95, abs=1e-9)
        assert state.recent_false_positives == 1

    def test_confidence_floor_respected(self) -> None:
        incidents = [{"id": f"fp-{i}", "false_positive": True, "resolved": True} for i in range(30)]
        state = self.sim.simulate_session(incidents)
        assert state.confidence_in_system >= 0.10

    def test_override_frequency_calculated_correctly(self) -> None:
        incidents = [
            {"id": "a", "override": True, "resolved": True},
            {"id": "b", "override": False, "resolved": True},
            {"id": "c", "override": True, "resolved": True},
            {"id": "d", "override": False, "resolved": True},
        ]
        state = self.sim.simulate_session(incidents)
        assert state.override_frequency == pytest.approx(0.5, abs=1e-9)

    def test_cognitive_load_formula(self) -> None:
        incidents = [
            {"id": "a", "resolved": True},
            {"id": "b", "resolved": True},
        ]
        state = self.sim.simulate_session(incidents)
        expected = min(
            1.0,
            0.4 * state.fatigue_score
            + 0.3 * state.escalation_pressure
            + 0.3 * state.override_frequency,
        )
        assert state.cognitive_load == pytest.approx(expected, abs=1e-9)

    def test_escalation_pressure_rises_above_threshold(self) -> None:
        incidents = [{"id": f"inc-{i}", "resolved": False} for i in range(5)]
        state = self.sim.simulate_session(incidents)
        assert state.escalation_pressure > 0.0

    def test_resolved_incidents_leave_active_list(self) -> None:
        incidents = [{"id": "x", "resolved": True}]
        state = self.sim.simulate_session(incidents)
        assert "x" not in state.active_incidents

    def test_unresolved_incidents_remain_in_active_list(self) -> None:
        incidents = [{"id": "y", "resolved": False}]
        state = self.sim.simulate_session(incidents)
        assert "y" in state.active_incidents


# ---------------------------------------------------------------------------
# DecisionLifecycleTracker
# ---------------------------------------------------------------------------


class TestDecisionLifecycleTracker:
    def setup_method(self) -> None:
        self.tracker = DecisionLifecycleTracker()

    def test_record_event_returns_decision_event(self) -> None:
        event = self.tracker.record_event(
            "inc-001", DecisionStage.RECOMMENDATION_RECEIVED, 0.0, {"source": "ai"}
        )
        assert isinstance(event, DecisionEvent)
        assert event.stage == DecisionStage.RECOMMENDATION_RECEIVED
        assert event.incident_id == "inc-001"

    def test_get_lifecycle_unknown_incident_returns_empty(self) -> None:
        lc = self.tracker.get_lifecycle("nonexistent")
        assert lc.events == []
        assert lc.is_complete is False
        assert lc.final_stage is None
        assert lc.total_elapsed_seconds == 0.0

    def test_lifecycle_not_complete_until_terminal_stage(self) -> None:
        self.tracker.record_event("inc-002", DecisionStage.OPERATOR_REVIEW_STARTED, 5.0)
        lc = self.tracker.get_lifecycle("inc-002")
        assert lc.is_complete is False

    def test_lifecycle_complete_on_incident_closed(self) -> None:
        self.tracker.record_event("inc-003", DecisionStage.RECOMMENDATION_RECEIVED, 0.0)
        self.tracker.record_event("inc-003", DecisionStage.INCIDENT_CLOSED, 120.0)
        lc = self.tracker.get_lifecycle("inc-003")
        assert lc.is_complete is True
        assert lc.final_stage == DecisionStage.INCIDENT_CLOSED

    def test_lifecycle_complete_on_rollback_triggered(self) -> None:
        self.tracker.record_event("inc-004", DecisionStage.ROLLBACK_TRIGGERED, 60.0)
        lc = self.tracker.get_lifecycle("inc-004")
        assert lc.is_complete is True

    def test_total_elapsed_seconds_reflects_last_event(self) -> None:
        self.tracker.record_event("inc-005", DecisionStage.RECOMMENDATION_RECEIVED, 0.0)
        self.tracker.record_event("inc-005", DecisionStage.REMEDIATION_EXECUTED, 90.0)
        lc = self.tracker.get_lifecycle("inc-005")
        assert lc.total_elapsed_seconds == pytest.approx(90.0)

    def test_all_lifecycles_returns_all(self) -> None:
        self.tracker.record_event("inc-A", DecisionStage.RECOMMENDATION_RECEIVED, 0.0)
        self.tracker.record_event("inc-B", DecisionStage.RECOMMENDATION_RECEIVED, 0.0)
        all_lc = self.tracker.all_lifecycles()
        incident_ids = {lc.incident_id for lc in all_lc}
        assert {"inc-A", "inc-B"}.issubset(incident_ids)

    def test_mean_time_to_stage_none_when_no_incidents(self) -> None:
        result = self.tracker.mean_time_to_stage(DecisionStage.INCIDENT_CLOSED)
        assert result is None

    def test_mean_time_to_stage_correct(self) -> None:
        self.tracker.record_event("i1", DecisionStage.RECOMMENDATION_RECEIVED, 0.0)
        self.tracker.record_event("i1", DecisionStage.REMEDIATION_EXECUTED, 30.0)
        self.tracker.record_event("i2", DecisionStage.RECOMMENDATION_RECEIVED, 0.0)
        self.tracker.record_event("i2", DecisionStage.REMEDIATION_EXECUTED, 50.0)
        mean = self.tracker.mean_time_to_stage(DecisionStage.REMEDIATION_EXECUTED)
        assert mean == pytest.approx(40.0)

    def test_mean_time_to_stage_none_when_stage_never_reached(self) -> None:
        self.tracker.record_event("i3", DecisionStage.RECOMMENDATION_RECEIVED, 0.0)
        result = self.tracker.mean_time_to_stage(DecisionStage.INCIDENT_CLOSED)
        assert result is None

    def test_metadata_stored_on_event(self) -> None:
        meta = {"triggered_by": "threshold_breach"}
        event = self.tracker.record_event("i4", DecisionStage.ESCALATION_TRIGGERED, 15.0, meta)
        assert event.metadata == meta


# ---------------------------------------------------------------------------
# SessionManager
# ---------------------------------------------------------------------------


class TestSessionManager:
    def setup_method(self) -> None:
        self.mgr = SessionManager()

    def test_create_session_returns_initial_phase(self) -> None:
        session = self.mgr.create_session("op-1")
        assert session.phase == SessionPhase.INITIAL
        assert session.operator_id == "op-1"
        assert session.incidents_handled == 0

    def test_session_becomes_active_after_first_incident(self) -> None:
        session = self.mgr.create_session("op-2")
        self.mgr.handle_incident(session.session_id, {"id": "inc-1"}, 10.0)
        phase = self.mgr.get_session_phase(session.session_id)
        assert phase == SessionPhase.ACTIVE

    def test_session_becomes_fatigued_after_many_incidents(self) -> None:
        session = self.mgr.create_session("op-3")
        sid = session.session_id
        for i in range(9):
            self.mgr.handle_incident(sid, {"id": f"inc-{i}"}, 5.0)
        phase = self.mgr.get_session_phase(sid)
        assert phase == SessionPhase.FATIGUED

    def test_session_overloaded_when_high_override_rate(self) -> None:
        session = self.mgr.create_session("op-4")
        sid = session.session_id
        for i in range(6):
            self.mgr.handle_incident(sid, {"id": f"inc-{i}"}, 5.0)
        for _ in range(4):
            self.mgr.record_override(sid)
        phase = self.mgr.get_session_phase(sid)
        assert phase == SessionPhase.OVERLOADED

    def test_record_override_increments_count(self) -> None:
        session = self.mgr.create_session("op-5")
        sid = session.session_id
        self.mgr.record_override(sid)
        self.mgr.record_override(sid)
        assert self.mgr._sessions[sid].overrides_issued == 2

    def test_record_escalation_increments_count(self) -> None:
        session = self.mgr.create_session("op-6")
        sid = session.session_id
        self.mgr.record_escalation(sid)
        assert self.mgr._sessions[sid].escalations_triggered == 1

    def test_record_false_positive_increments_count(self) -> None:
        session = self.mgr.create_session("op-7")
        sid = session.session_id
        self.mgr.record_false_positive(sid)
        self.mgr.record_false_positive(sid)
        assert self.mgr._sessions[sid].false_positives_encountered == 2

    def test_close_session_sets_completed_phase(self) -> None:
        session = self.mgr.create_session("op-8")
        sid = session.session_id
        self.mgr.handle_incident(sid, {"id": "inc-x"}, 5.0)
        closed = self.mgr.close_session(sid)
        assert closed.phase == SessionPhase.COMPLETED

    def test_response_time_accumulates(self) -> None:
        session = self.mgr.create_session("op-9")
        sid = session.session_id
        self.mgr.handle_incident(sid, {"id": "a"}, 10.0)
        self.mgr.handle_incident(sid, {"id": "b"}, 20.0)
        assert self.mgr._sessions[sid].total_response_time_seconds == pytest.approx(30.0)

    def test_context_switches_tracked_on_incident_change(self) -> None:
        session = self.mgr.create_session("op-10")
        sid = session.session_id
        self.mgr.handle_incident(sid, {"id": "x"}, 5.0)
        self.mgr.handle_incident(sid, {"id": "y"}, 5.0)
        assert self.mgr._sessions[sid].context_switches == 1

    def test_unknown_session_raises_key_error(self) -> None:
        with pytest.raises(KeyError):
            self.mgr.handle_incident("ghost-id", {"id": "x"}, 1.0)


# ---------------------------------------------------------------------------
# EscalationChain
# ---------------------------------------------------------------------------


class TestEscalationChain:
    def setup_method(self) -> None:
        self.chain = EscalationChain()

    def test_start_incident_creates_pathway_at_l1(self) -> None:
        pathway = self.chain.start_incident("inc-alpha")
        assert pathway.current_level == EscalationLevel.L1_AUTOMATED
        assert pathway.total_escalations == 0
        assert pathway.is_escalating is False

    def test_escalate_moves_level_up(self) -> None:
        self.chain.start_incident("inc-beta")
        step = self.chain.escalate("inc-beta", "threshold breach", "auto_trigger", 30.0)
        pathway = self.chain.get_pathway("inc-beta")
        assert pathway.current_level == EscalationLevel.L2_OPERATOR
        assert step.from_level == EscalationLevel.L1_AUTOMATED
        assert step.to_level == EscalationLevel.L2_OPERATOR

    def test_escalate_increments_total_escalations(self) -> None:
        self.chain.start_incident("inc-gamma")
        self.chain.escalate("inc-gamma", "r1", "t1", 10.0)
        self.chain.escalate("inc-gamma", "r2", "t2", 20.0)
        pathway = self.chain.get_pathway("inc-gamma")
        assert pathway.total_escalations == 2

    def test_escalate_caps_at_l5(self) -> None:
        self.chain.start_incident("inc-delta")
        for i in range(10):
            self.chain.escalate("inc-delta", f"reason-{i}", "trigger", float(i * 10))
        pathway = self.chain.get_pathway("inc-delta")
        assert pathway.current_level == EscalationLevel.L5_EXECUTIVE

    def test_de_escalate_moves_level_down(self) -> None:
        self.chain.start_incident("inc-eps")
        self.chain.escalate("inc-eps", "r", "t", 10.0)
        self.chain.escalate("inc-eps", "r", "t", 20.0)
        self.chain.de_escalate("inc-eps")
        pathway = self.chain.get_pathway("inc-eps")
        assert pathway.current_level == EscalationLevel.L2_OPERATOR

    def test_de_escalate_does_not_go_below_l2(self) -> None:
        self.chain.start_incident("inc-zeta")
        self.chain.escalate("inc-zeta", "r", "t", 10.0)
        self.chain.de_escalate("inc-zeta")
        pathway = self.chain.get_pathway("inc-zeta")
        assert pathway.current_level == EscalationLevel.L2_OPERATOR
        self.chain.de_escalate("inc-zeta")
        pathway = self.chain.get_pathway("inc-zeta")
        assert pathway.current_level == EscalationLevel.L2_OPERATOR

    def test_escalation_summary_empty_chain(self) -> None:
        summary = self.chain.escalation_summary()
        assert summary["mean_escalations"] == 0.0
        assert summary["max_level_reached"] is None
        assert summary["escalation_spam_rate"] == 0.0

    def test_escalation_summary_mean_escalations(self) -> None:
        self.chain.start_incident("s1")
        self.chain.escalate("s1", "r", "t", 10.0)
        self.chain.escalate("s1", "r", "t", 20.0)
        self.chain.start_incident("s2")
        self.chain.escalate("s2", "r", "t", 10.0)
        summary = self.chain.escalation_summary()
        assert summary["mean_escalations"] == pytest.approx(1.5)

    def test_escalation_summary_max_level(self) -> None:
        self.chain.start_incident("m1")
        self.chain.escalate("m1", "r", "t", 10.0)
        self.chain.escalate("m1", "r", "t", 20.0)
        self.chain.escalate("m1", "r", "t", 30.0)
        self.chain.start_incident("m2")
        self.chain.escalate("m2", "r", "t", 5.0)
        summary = self.chain.escalation_summary()
        assert summary["max_level_reached"] == EscalationLevel.L4_INCIDENT_COMMANDER

    def test_escalation_spam_rate(self) -> None:
        self.chain.start_incident("sp1")
        for i in range(3):
            self.chain.escalate("sp1", "r", "t", float(i))
        self.chain.start_incident("sp2")
        self.chain.escalate("sp2", "r", "t", 1.0)
        summary = self.chain.escalation_summary()
        assert summary["escalation_spam_rate"] == pytest.approx(0.5)

    def test_get_pathway_unknown_raises(self) -> None:
        with pytest.raises(KeyError):
            self.chain.get_pathway("nonexistent")

    def test_step_stores_reason_and_trigger(self) -> None:
        self.chain.start_incident("detail-inc")
        step = self.chain.escalate("detail-inc", "cpu_spike", "threshold_90pct", 45.0)
        assert step.reason == "cpu_spike"
        assert step.trigger == "threshold_90pct"
        assert step.elapsed_seconds == pytest.approx(45.0)
