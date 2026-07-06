"""Tests for operator interaction replay (Phase 47 Commit 4)."""

from __future__ import annotations

from operators.approval_latency import ApprovalLatencyAnalyzer
from operators.intervention_tracker import (
    InterventionKind,
    InterventionTracker,
    OperatorIntervention,
)
from operators.operator_replay import OperatorReplayEngine, ReplayStep
from operators.override_analysis import OverrideAnalyzer

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _iv(
    incident_id: str = "INC-1",
    operator_id: str = "op-1",
    kind: InterventionKind = InterventionKind.APPROVE,
    mechanism: str = "restart_service",
    confidence: float = 0.75,
    ts: str = "2026-05-01T10:00:00Z",
    ai_rec: str = "restart",
) -> OperatorIntervention:
    return OperatorIntervention(
        intervention_id=f"iv_{ts}_{kind.value}",
        incident_id=incident_id,
        operator_id=operator_id,
        kind=kind,
        timestamp_iso=ts,
        target_mechanism=mechanism,
        confidence_at_time=confidence,
        ai_recommendation=ai_rec,
    )


# ---------------------------------------------------------------------------
# InterventionTracker
# ---------------------------------------------------------------------------


class TestInterventionTracker:
    def test_record_and_retrieve(self):
        tracker = InterventionTracker()
        tracker.record(_iv())
        assert len(tracker.all_interventions()) == 1

    def test_for_incident(self):
        tracker = InterventionTracker()
        tracker.record(_iv(incident_id="INC-1"))
        tracker.record(_iv(incident_id="INC-2"))
        assert len(tracker.for_incident("INC-1")) == 1

    def test_for_operator(self):
        tracker = InterventionTracker()
        tracker.record(_iv(operator_id="op-1"))
        tracker.record(_iv(operator_id="op-2"))
        assert len(tracker.for_operator("op-1")) == 1

    def test_by_kind(self):
        tracker = InterventionTracker()
        tracker.record(_iv(kind=InterventionKind.APPROVE))
        tracker.record(_iv(kind=InterventionKind.REJECT))
        approvals = tracker.by_kind(InterventionKind.APPROVE)
        assert len(approvals) == 1

    def test_overrides(self):
        tracker = InterventionTracker()
        tracker.record(_iv(kind=InterventionKind.APPROVE))
        tracker.record(_iv(kind=InterventionKind.OVERRIDE))
        tracker.record(_iv(kind=InterventionKind.REJECT))
        assert len(tracker.overrides()) == 2

    def test_approvals(self):
        tracker = InterventionTracker()
        tracker.record(_iv(kind=InterventionKind.APPROVE))
        tracker.record(_iv(kind=InterventionKind.OVERRIDE))
        assert len(tracker.approvals()) == 1

    def test_record_action(self):
        tracker = InterventionTracker()
        iv = tracker.record_action(
            incident_id="INC-1",
            operator_id="op-1",
            kind=InterventionKind.ESCALATE,
            target_mechanism="db_failover",
            confidence_at_time=0.60,
        )
        assert iv.incident_id == "INC-1"
        assert iv.kind == InterventionKind.ESCALATE

    def test_summarize_rates(self):
        tracker = InterventionTracker()
        for _ in range(6):
            tracker.record(_iv(kind=InterventionKind.APPROVE))
        for _ in range(4):
            tracker.record(_iv(kind=InterventionKind.OVERRIDE))
        summary = tracker.summarize()
        assert abs(summary.approval_rate - 0.60) < 0.01
        assert abs(summary.override_rate - 0.40) < 0.01

    def test_summarize_empty(self):
        tracker = InterventionTracker()
        summary = tracker.summarize()
        assert summary.total == 0
        assert summary.override_rate == 0.0

    def test_clear(self):
        tracker = InterventionTracker()
        tracker.record(_iv())
        tracker.clear()
        assert len(tracker.all_interventions()) == 0

    def test_is_override_property(self):
        reject_iv = _iv(kind=InterventionKind.REJECT)
        assert reject_iv.is_override
        override_iv = _iv(kind=InterventionKind.OVERRIDE)
        assert override_iv.is_override
        approve_iv = _iv(kind=InterventionKind.APPROVE)
        assert not approve_iv.is_override

    def test_is_escalation_property(self):
        esc_iv = _iv(kind=InterventionKind.ESCALATE)
        assert esc_iv.is_escalation


# ---------------------------------------------------------------------------
# OperatorReplayEngine
# ---------------------------------------------------------------------------


class TestOperatorReplayEngine:
    def _ivs_for_incident(self) -> list[OperatorIntervention]:
        return [
            _iv(kind=InterventionKind.ACKNOWLEDGE, ts="2026-05-01T10:00:00Z"),
            _iv(kind=InterventionKind.APPROVE, ts="2026-05-01T10:01:00Z"),
            _iv(kind=InterventionKind.OVERRIDE, ts="2026-05-01T10:02:00Z"),
        ]

    def test_replay_incident_step_count(self):
        engine = OperatorReplayEngine()
        session = engine.replay_incident("INC-1", self._ivs_for_incident())
        assert session.total_steps == 3

    def test_replay_incident_override_count(self):
        engine = OperatorReplayEngine()
        session = engine.replay_incident("INC-1", self._ivs_for_incident())
        assert session.override_count == 1

    def test_replay_incident_approval_count(self):
        engine = OperatorReplayEngine()
        session = engine.replay_incident("INC-1", self._ivs_for_incident())
        assert session.approval_count == 1

    def test_replay_incident_override_rate(self):
        engine = OperatorReplayEngine()
        session = engine.replay_incident("INC-1", self._ivs_for_incident())
        assert abs(session.override_rate - 1 / 3) < 0.01

    def test_replay_incident_chronological(self):
        engine = OperatorReplayEngine()
        ivs = [
            _iv(kind=InterventionKind.APPROVE, ts="2026-05-01T10:02:00Z"),
            _iv(kind=InterventionKind.ACKNOWLEDGE, ts="2026-05-01T10:00:00Z"),
        ]
        session = engine.replay_incident("INC-1", ivs)
        assert session.steps[0].intervention.kind == InterventionKind.ACKNOWLEDGE

    def test_replay_callback_fires(self):
        engine = OperatorReplayEngine()
        fired: list[ReplayStep] = []
        engine.register_callback(fired.append)
        engine.replay_incident("INC-1", self._ivs_for_incident())
        assert len(fired) == 3

    def test_cumulative_overrides_in_steps(self):
        engine = OperatorReplayEngine()
        session = engine.replay_incident("INC-1", self._ivs_for_incident())
        last_step = session.steps[-1]
        assert last_step.cumulative_overrides == 1

    def test_has_rollback_false(self):
        engine = OperatorReplayEngine()
        session = engine.replay_incident("INC-1", self._ivs_for_incident())
        assert not session.has_rollback

    def test_has_rollback_true(self):
        engine = OperatorReplayEngine()
        ivs = [_iv(kind=InterventionKind.ROLLBACK, ts="2026-05-01T10:03:00Z")]
        session = engine.replay_incident("INC-1", ivs)
        assert session.has_rollback

    def test_replay_operator_groups_by_incident(self):
        engine = OperatorReplayEngine()
        ivs = [
            _iv(incident_id="INC-1", ts="2026-05-01T10:00:00Z"),
            _iv(incident_id="INC-2", ts="2026-05-01T10:01:00Z"),
        ]
        sessions = engine.replay_operator("op-1", ivs)
        assert "INC-1" in sessions
        assert "INC-2" in sessions

    def test_elapsed_seconds_monotone(self):
        engine = OperatorReplayEngine()
        session = engine.replay_incident("INC-1", self._ivs_for_incident())
        elapsed = [s.elapsed_seconds for s in session.steps]
        assert elapsed == sorted(elapsed)

    def test_override_before_step(self):
        engine = OperatorReplayEngine()
        session = engine.replay_incident("INC-1", self._ivs_for_incident())
        # Step 2 is the override; checking before step 2 should return 0
        assert session.override_before_step(2) == 0


# ---------------------------------------------------------------------------
# OverrideAnalyzer
# ---------------------------------------------------------------------------


class TestOverrideAnalyzer:
    def _make_ivs(
        self, mechanism: str, n_approve: int, n_override: int, confidence: float = 0.75
    ) -> list[OperatorIntervention]:
        ivs = []
        for _ in range(n_approve):
            ivs.append(
                _iv(
                    kind=InterventionKind.APPROVE,
                    mechanism=mechanism,
                    confidence=confidence,
                )
            )
        for _ in range(n_override):
            ivs.append(
                _iv(
                    kind=InterventionKind.OVERRIDE,
                    mechanism=mechanism,
                    confidence=confidence,
                )
            )
        return ivs

    def test_override_rate(self):
        analyzer = OverrideAnalyzer()
        ivs = self._make_ivs("restart", n_approve=6, n_override=4)
        report = analyzer.analyze(ivs)
        assert abs(report.overall_override_rate - 0.40) < 0.01

    def test_systematic_mechanism_detected(self):
        analyzer = OverrideAnalyzer()
        ivs = self._make_ivs("restart", n_approve=2, n_override=8)
        report = analyzer.analyze(ivs)
        assert "restart" in report.systematic_mechanisms

    def test_non_systematic_not_flagged(self):
        analyzer = OverrideAnalyzer()
        ivs = self._make_ivs("scale_out", n_approve=8, n_override=1)
        report = analyzer.analyze(ivs)
        assert "scale_out" not in report.systematic_mechanisms

    def test_high_confidence_overrides(self):
        analyzer = OverrideAnalyzer()
        ivs = [_iv(kind=InterventionKind.OVERRIDE, confidence=0.85)]
        report = analyzer.analyze(ivs)
        assert report.high_confidence_overrides == 1

    def test_low_confidence_approvals(self):
        analyzer = OverrideAnalyzer()
        ivs = [_iv(kind=InterventionKind.APPROVE, confidence=0.40)]
        report = analyzer.analyze(ivs)
        assert report.low_confidence_approvals == 1

    def test_top_overriding_operators(self):
        analyzer = OverrideAnalyzer()
        ivs = [
            _iv(operator_id="op-1", kind=InterventionKind.OVERRIDE),
            _iv(operator_id="op-1", kind=InterventionKind.OVERRIDE),
            _iv(operator_id="op-2", kind=InterventionKind.OVERRIDE),
        ]
        report = analyzer.analyze(ivs)
        assert report.top_overriding_operators[0][0] == "op-1"

    def test_operator_override_rates(self):
        analyzer = OverrideAnalyzer()
        ivs = [
            _iv(operator_id="op-1", kind=InterventionKind.OVERRIDE),
            _iv(operator_id="op-1", kind=InterventionKind.APPROVE),
            _iv(operator_id="op-2", kind=InterventionKind.APPROVE),
        ]
        rates = analyzer.operator_override_rates(ivs)
        assert abs(rates["op-1"] - 0.50) < 0.01
        assert rates["op-2"] == 0.0

    def test_mechanisms_with_high_override(self):
        analyzer = OverrideAnalyzer()
        ivs = self._make_ivs("bad_mech", n_approve=1, n_override=9) + self._make_ivs(
            "good_mech", n_approve=9, n_override=1
        )
        mechanisms = analyzer.mechanisms_with_high_override(ivs, min_rate=0.40)
        assert "bad_mech" in mechanisms
        assert "good_mech" not in mechanisms

    def test_empty_interventions(self):
        analyzer = OverrideAnalyzer()
        report = analyzer.analyze([])
        assert report.total_interventions == 0
        assert report.overall_override_rate == 0.0


# ---------------------------------------------------------------------------
# ApprovalLatencyAnalyzer
# ---------------------------------------------------------------------------


class TestApprovalLatencyAnalyzer:
    def _make_iv(
        self,
        kind: InterventionKind = InterventionKind.APPROVE,
        ts: str = "2026-05-01T10:05:00Z",
    ) -> OperatorIntervention:
        return _iv(kind=kind, ts=ts)

    def test_single_latency(self):
        analyzer = ApprovalLatencyAnalyzer()
        iv = self._make_iv(ts="2026-05-01T10:05:00Z")
        sample = analyzer.ingest(iv, ai_emit_timestamp_iso="2026-05-01T10:00:00Z")
        assert sample is not None
        assert abs(sample.latency_seconds - 300.0) < 1.0

    def test_latency_report_mean(self):
        analyzer = ApprovalLatencyAnalyzer()
        analyzer.ingest(
            self._make_iv(ts="2026-05-01T10:05:00Z"),
            "2026-05-01T10:00:00Z",
        )
        analyzer.ingest(
            self._make_iv(ts="2026-05-01T10:10:00Z"),
            "2026-05-01T10:00:00Z",
        )
        report = analyzer.report()
        assert abs(report.mean_latency_seconds - 450.0) < 1.0

    def test_slow_rate(self):
        analyzer = ApprovalLatencyAnalyzer(slow_threshold_seconds=60.0)
        analyzer.ingest(
            self._make_iv(ts="2026-05-01T10:10:00Z"),
            "2026-05-01T10:00:00Z",
        )  # 600s > 60s → slow
        report = analyzer.report()
        assert report.slow_rate == 1.0

    def test_is_responsive(self):
        analyzer = ApprovalLatencyAnalyzer(slow_threshold_seconds=600.0)
        analyzer.ingest(
            self._make_iv(ts="2026-05-01T10:02:00Z"),
            "2026-05-01T10:00:00Z",
        )  # 120s < 600s
        report = analyzer.report()
        assert report.is_responsive

    def test_empty_report(self):
        analyzer = ApprovalLatencyAnalyzer()
        report = analyzer.report()
        assert report.total_samples == 0

    def test_negative_latency_skipped(self):
        analyzer = ApprovalLatencyAnalyzer()
        iv = self._make_iv(ts="2026-05-01T09:55:00Z")
        # IV timestamp before AI emission
        sample = analyzer.ingest(iv, ai_emit_timestamp_iso="2026-05-01T10:00:00Z")
        assert sample is None

    def test_by_kind_in_report(self):
        analyzer = ApprovalLatencyAnalyzer()
        analyzer.ingest(
            self._make_iv(kind=InterventionKind.APPROVE, ts="2026-05-01T10:05:00Z"),
            "2026-05-01T10:00:00Z",
        )
        analyzer.ingest(
            self._make_iv(kind=InterventionKind.REJECT, ts="2026-05-01T10:03:00Z"),
            "2026-05-01T10:00:00Z",
        )
        report = analyzer.report()
        assert "approve" in report.by_kind
        assert "reject" in report.by_kind

    def test_per_operator_report(self):
        analyzer = ApprovalLatencyAnalyzer()
        iv1 = _iv(operator_id="op-1", ts="2026-05-01T10:05:00Z")
        iv2 = _iv(operator_id="op-2", ts="2026-05-01T10:10:00Z")
        analyzer.ingest(iv1, "2026-05-01T10:00:00Z")
        analyzer.ingest(iv2, "2026-05-01T10:00:00Z")
        per_op = analyzer.per_operator_report()
        assert "op-1" in per_op
        assert "op-2" in per_op

    def test_clear(self):
        analyzer = ApprovalLatencyAnalyzer()
        analyzer.ingest(
            self._make_iv(ts="2026-05-01T10:05:00Z"),
            "2026-05-01T10:00:00Z",
        )
        analyzer.clear()
        assert analyzer.report().total_samples == 0

    def test_p90_latency(self):
        analyzer = ApprovalLatencyAnalyzer()
        for minutes in range(1, 11):
            ts = f"2026-05-01T10:{minutes:02d}:00Z"
            analyzer.ingest(self._make_iv(ts=ts), "2026-05-01T10:00:00Z")
        report = analyzer.report()
        # 10 samples, 60-600s; p90 should be around the 9th sample (540s)
        assert report.p90_latency_seconds >= 540.0
