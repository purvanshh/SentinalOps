"""Tests for TrustAdaptationEngine (Phase 46)."""

from __future__ import annotations

from learning.feedback_engine import FeedbackKind, FeedbackRecord
from learning.outcome_memory import OutcomeRecord
from learning.trust_adaptation import TrustAdaptationEngine


def _feedback(kind: FeedbackKind, mechanism_id: str = "memory_pressure") -> FeedbackRecord:
    return FeedbackRecord(
        incident_id="INC-001",
        feedback_kind=kind,
        mechanism_id=mechanism_id,
        remediation_class="scale_replicas",
        incident_category="performance",
        ai_confidence=0.75,
        operator_id="ops-1",
    )


def _outcome(success: bool, harmful: bool = False) -> OutcomeRecord:
    return OutcomeRecord(
        outcome_id="OUT-001",
        incident_id="INC-001",
        remediation_class="scale_replicas",
        mechanism_id="memory_pressure",
        incident_category="performance",
        success=success,
        required_rollback=harmful,
    )


class TestTrustAdaptationEngine:
    def test_initial_trust_is_neutral(self):
        engine = TrustAdaptationEngine()
        assert engine.mechanism_trust("unknown") == 0.50
        assert engine.remediation_trust("unknown") == 0.50

    def test_rollback_feedback_decreases_mechanism_trust(self):
        engine = TrustAdaptationEngine()
        engine.update_from_feedback(_feedback(FeedbackKind.ROLLBACK))
        assert engine.mechanism_trust("memory_pressure") < 0.50

    def test_approval_feedback_slightly_increases_trust(self):
        engine = TrustAdaptationEngine()
        engine.update_from_feedback(_feedback(FeedbackKind.APPROVAL))
        assert engine.mechanism_trust("memory_pressure") > 0.50

    def test_trust_bounded_below_by_min(self):
        engine = TrustAdaptationEngine()
        for i in range(50):
            engine.update_from_feedback(
                FeedbackRecord(
                    incident_id=f"INC-{i:03d}",
                    feedback_kind=FeedbackKind.ROLLBACK,
                    mechanism_id="retry_storm",
                    remediation_class="scale_replicas",
                    incident_category="availability",
                    ai_confidence=0.80,
                    operator_id="ops-1",
                )
            )
        assert engine.mechanism_trust("retry_storm") >= 0.10

    def test_trust_bounded_above_by_max(self):
        engine = TrustAdaptationEngine()
        for i in range(50):
            engine.update_from_feedback(
                FeedbackRecord(
                    incident_id=f"INC-{i:03d}",
                    feedback_kind=FeedbackKind.APPROVAL,
                    mechanism_id="memory_pressure",
                    remediation_class="scale_replicas",
                    incident_category="performance",
                    ai_confidence=0.75,
                    operator_id="ops-1",
                )
            )
        assert engine.mechanism_trust("memory_pressure") <= 0.95

    def test_outcome_harmful_decreases_trust(self):
        engine = TrustAdaptationEngine()
        engine.update_from_outcome(_outcome(success=False, harmful=True))
        assert engine.mechanism_trust("memory_pressure") < 0.50

    def test_outcome_success_increases_trust(self):
        engine = TrustAdaptationEngine()
        engine.update_from_outcome(_outcome(success=True))
        assert engine.mechanism_trust("memory_pressure") > 0.50

    def test_update_produces_trust_update_events(self):
        engine = TrustAdaptationEngine()
        events = engine.update_from_feedback(_feedback(FeedbackKind.REJECTION))
        assert len(events) == 2  # one for mechanism, one for remediation

    def test_update_event_contains_reason_code(self):
        engine = TrustAdaptationEngine()
        events = engine.update_from_feedback(_feedback(FeedbackKind.REJECTION))
        assert any("feedback_rejection" in ev.reason_code for ev in events)

    def test_dampened_flag_set_when_few_samples(self):
        engine = TrustAdaptationEngine()
        events = engine.update_from_feedback(_feedback(FeedbackKind.ROLLBACK))
        mech_events = [ev for ev in events if ev.key_type == "mechanism"]
        assert mech_events[0].dampened is True

    def test_dampened_flag_cleared_after_enough_samples(self):
        engine = TrustAdaptationEngine()
        for i in range(6):
            engine.update_from_feedback(
                FeedbackRecord(
                    incident_id=f"INC-{i:03d}",
                    feedback_kind=FeedbackKind.APPROVAL,
                    mechanism_id="memory_pressure",
                    remediation_class="scale_replicas",
                    incident_category="performance",
                    ai_confidence=0.75,
                    operator_id="ops-1",
                )
            )
        ts = engine.trust_score_for_mechanism("memory_pressure")
        assert ts.sample_size_warning is False

    def test_trust_score_for_mechanism(self):
        engine = TrustAdaptationEngine()
        engine.update_from_feedback(_feedback(FeedbackKind.REJECTION))
        score = engine.trust_score_for_mechanism("memory_pressure")
        assert score.key == "memory_pressure"
        assert score.key_type == "mechanism"
        assert 0.10 <= score.score <= 0.95

    def test_confidence_modifier_positive_for_high_trust(self):
        engine = TrustAdaptationEngine()
        # Force high trust by inserting many approvals
        for i in range(30):
            engine.update_from_feedback(
                FeedbackRecord(
                    incident_id=f"INC-{i:03d}",
                    feedback_kind=FeedbackKind.APPROVAL,
                    mechanism_id="memory_pressure",
                    remediation_class="scale_replicas",
                    incident_category="performance",
                    ai_confidence=0.75,
                    operator_id="ops-1",
                )
            )
        modifier = engine.confidence_modifier_for_mechanism("memory_pressure")
        assert modifier >= 0.0

    def test_confidence_modifier_negative_for_low_trust(self):
        engine = TrustAdaptationEngine()
        for i in range(30):
            engine.update_from_feedback(
                FeedbackRecord(
                    incident_id=f"INC-{i:03d}",
                    feedback_kind=FeedbackKind.ROLLBACK,
                    mechanism_id="retry_storm",
                    remediation_class="scale_replicas",
                    incident_category="availability",
                    ai_confidence=0.80,
                    operator_id="ops-1",
                )
            )
        modifier = engine.confidence_modifier_for_mechanism("retry_storm")
        assert modifier <= 0.0

    def test_remediation_risk_modifier_negative_for_low_trust(self):
        engine = TrustAdaptationEngine()
        for i in range(20):
            engine.update_from_feedback(
                FeedbackRecord(
                    incident_id=f"INC-{i:03d}",
                    feedback_kind=FeedbackKind.ROLLBACK,
                    mechanism_id=None,
                    remediation_class="flush_cache",
                    incident_category="performance",
                    ai_confidence=0.65,
                    operator_id="ops-1",
                )
            )
        modifier = engine.remediation_risk_modifier("flush_cache")
        assert modifier <= 0.0

    def test_decay_toward_neutral(self):
        engine = TrustAdaptationEngine()
        engine.update_from_feedback(_feedback(FeedbackKind.ROLLBACK))
        trust_before = engine.mechanism_trust("memory_pressure")
        engine.decay_toward_neutral(mechanism_ids=["memory_pressure"])
        trust_after = engine.mechanism_trust("memory_pressure")
        # After decay, trust should be closer to 0.50
        assert abs(trust_after - 0.50) <= abs(trust_before - 0.50)

    def test_snapshot_serializable(self):
        engine = TrustAdaptationEngine()
        engine.update_from_feedback(_feedback(FeedbackKind.APPROVAL))
        snap = engine.snapshot()
        assert "mechanism_trust" in snap
        assert "remediation_trust" in snap
        assert "memory_pressure" in snap["mechanism_trust"]

    def test_batch_feedback(self):
        engine = TrustAdaptationEngine()
        records = [_feedback(FeedbackKind.REJECTION, f"mech_{i}") for i in range(3)]
        events = engine.apply_feedback_batch(records)
        assert len(events) >= 3
