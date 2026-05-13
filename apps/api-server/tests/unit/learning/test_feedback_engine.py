"""Tests for OperatorFeedbackEngine (Phase 46)."""

from __future__ import annotations

import pytest
from learning.feedback_engine import (
    FeedbackKind,
    FeedbackRecord,
    OperatorFeedbackEngine,
)


def _approval(incident_id: str = "INC-001", confidence: float = 0.80) -> FeedbackRecord:
    return FeedbackRecord(
        incident_id=incident_id,
        feedback_kind=FeedbackKind.APPROVAL,
        mechanism_id="memory_pressure",
        remediation_class="scale_replicas",
        incident_category="performance",
        ai_confidence=confidence,
        operator_id="ops-1",
    )


def _rejection(incident_id: str = "INC-002", confidence: float = 0.70) -> FeedbackRecord:
    return FeedbackRecord(
        incident_id=incident_id,
        feedback_kind=FeedbackKind.REJECTION,
        mechanism_id="connection_pool_starvation",
        remediation_class="increase_pool_size",
        incident_category="availability",
        ai_confidence=confidence,
        operator_id="ops-1",
        note="wrong diagnosis",
    )


def _rollback(incident_id: str = "INC-003") -> FeedbackRecord:
    return FeedbackRecord(
        incident_id=incident_id,
        feedback_kind=FeedbackKind.ROLLBACK,
        mechanism_id="retry_storm",
        remediation_class="add_circuit_breaker",
        incident_category="availability",
        ai_confidence=0.65,
        operator_id="ops-2",
        required_rollback=True,
    )


class TestFeedbackKind:
    def test_all_kinds_exist(self):
        kinds = {k.value for k in FeedbackKind}
        assert "approval" in kinds
        assert "rejection" in kinds
        assert "override" in kinds
        assert "rollback" in kinds
        assert "manual_edit" in kinds
        assert "escalation" in kinds
        assert "false_positive_confirmation" in kinds

    def test_rollback_has_highest_signal_weight(self):
        rec = _rollback()
        assert rec.signal_weight == 1.0

    def test_approval_has_lowest_signal_weight(self):
        rec = _approval()
        assert rec.signal_weight == 0.1

    def test_rejection_signal_weight(self):
        rec = _rejection()
        assert rec.signal_weight == 0.8


class TestFeedbackRecord:
    def test_rollback_is_correction(self):
        assert _rollback().is_correction is True

    def test_rejection_is_correction(self):
        assert _rejection().is_correction is True

    def test_approval_is_not_correction(self):
        assert _approval().is_correction is False

    def test_to_dict_contains_all_keys(self):
        d = _approval().to_dict()
        for key in [
            "incident_id", "feedback_kind", "is_correction", "signal_weight",
            "ai_confidence", "operator_id",
        ]:
            assert key in d


class TestOperatorFeedbackEngine:
    def test_record_and_retrieve(self):
        engine = OperatorFeedbackEngine()
        rec = engine.record_approval(
            incident_id="INC-001",
            mechanism_id="memory_pressure",
            remediation_class="scale_replicas",
            incident_category="performance",
            ai_confidence=0.80,
            operator_id="ops-1",
        )
        assert len(engine.all_records()) == 1
        assert rec.feedback_kind == FeedbackKind.APPROVAL

    def test_record_rejection_stores_correctly(self):
        engine = OperatorFeedbackEngine()
        engine.record_rejection(
            incident_id="INC-002",
            mechanism_id="connection_pool_starvation",
            remediation_class="increase_pool_size",
            incident_category="availability",
            ai_confidence=0.70,
            operator_id="ops-1",
        )
        recs = engine.records_for_mechanism("connection_pool_starvation")
        assert len(recs) == 1

    def test_record_rollback_flags_required_rollback(self):
        engine = OperatorFeedbackEngine()
        rec = engine.record_rollback(
            incident_id="INC-003",
            mechanism_id="retry_storm",
            remediation_class="add_circuit_breaker",
            incident_category="availability",
            ai_confidence=0.65,
            operator_id="ops-2",
        )
        assert rec.required_rollback is True

    def test_record_false_positive(self):
        engine = OperatorFeedbackEngine()
        rec = engine.record_false_positive(
            incident_id="INC-004",
            incident_category="noise",
            ai_confidence=0.55,
            operator_id="ops-3",
        )
        assert rec.was_false_positive is True
        assert rec.mechanism_id is None

    def test_summarize_empty(self):
        engine = OperatorFeedbackEngine()
        summary = engine.summarize()
        assert summary.total_events == 0
        assert summary.correction_rate == 0.0

    def test_summarize_correction_rate(self):
        engine = OperatorFeedbackEngine()
        engine.record(_approval())
        engine.record(_rejection())
        engine.record(_rollback())
        summary = engine.summarize()
        # rejection + rollback are corrections = 2/3
        assert summary.correction_rate == pytest.approx(2 / 3, abs=0.01)

    def test_confidence_adjustment_negative_on_high_corrections(self):
        engine = OperatorFeedbackEngine()
        for i in range(4):
            engine.record(_rollback(f"INC-{i:03d}"))
        adj = engine.confidence_adjustment_for_mechanism("retry_storm")
        assert adj < 0.0

    def test_confidence_adjustment_bounded(self):
        engine = OperatorFeedbackEngine()
        for i in range(20):
            engine.record(_rollback(f"INC-{i:03d}"))
        adj = engine.confidence_adjustment_for_mechanism("retry_storm")
        assert adj >= -0.30
        assert adj <= 0.05

    def test_records_for_category(self):
        engine = OperatorFeedbackEngine()
        engine.record(_approval())
        engine.record(_rejection())
        perf_recs = engine.records_for_category("performance")
        avail_recs = engine.records_for_category("availability")
        assert len(perf_recs) == 1
        assert len(avail_recs) == 1

    def test_summarize_rollback_rate(self):
        engine = OperatorFeedbackEngine()
        engine.record(_approval())
        engine.record(_rollback())
        summary = engine.summarize()
        assert summary.rollback_rate == pytest.approx(0.5, abs=0.01)

    def test_summarize_mechanisms_with_corrections(self):
        engine = OperatorFeedbackEngine()
        engine.record(_rejection())
        engine.record(_rollback())
        summary = engine.summarize()
        assert "connection_pool_starvation" in summary.mechanisms_with_corrections
        assert "retry_storm" in summary.mechanisms_with_corrections
