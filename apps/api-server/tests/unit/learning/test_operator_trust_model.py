"""Tests for OperatorTrustModel (Phase 46)."""

from __future__ import annotations

import pytest
from learning.feedback_engine import FeedbackKind, FeedbackRecord
from learning.operator_trust_model import OperatorTrustModel


def _fb(
    incident_id: str,
    kind: FeedbackKind,
    operator_id: str = "ops-1",
    mechanism_id: str | None = "memory_pressure",
    remediation_class: str | None = "scale_replicas",
) -> FeedbackRecord:
    return FeedbackRecord(
        incident_id=incident_id,
        feedback_kind=kind,
        mechanism_id=mechanism_id,
        remediation_class=remediation_class,
        incident_category="performance",
        ai_confidence=0.75,
        operator_id=operator_id,
    )


class TestOperatorTrustModel:
    def test_empty_model_returns_default_profile(self):
        model = OperatorTrustModel()
        profile = model.operator_profile_for_mechanism("ops-1", "memory_pressure")
        assert profile.total_interactions == 0
        assert profile.agreement_rate == 0.5

    def test_ingest_approval(self):
        model = OperatorTrustModel()
        model.ingest(_fb("INC-001", FeedbackKind.APPROVAL))
        profile = model.operator_profile_for_mechanism("ops-1", "memory_pressure")
        assert profile.total_interactions == 1
        assert profile.agreement_count == 1
        assert profile.correction_count == 0

    def test_ingest_rejection_is_correction(self):
        model = OperatorTrustModel()
        model.ingest(_fb("INC-001", FeedbackKind.REJECTION))
        profile = model.operator_profile_for_mechanism("ops-1", "memory_pressure")
        assert profile.correction_count == 1

    def test_ingest_rollback_is_correction_and_rollback(self):
        model = OperatorTrustModel()
        model.ingest(_fb("INC-001", FeedbackKind.ROLLBACK))
        profile = model.operator_profile_for_mechanism("ops-1", "memory_pressure")
        assert profile.rollback_count == 1
        assert profile.correction_count == 1

    def test_agreement_rate_computed(self):
        model = OperatorTrustModel()
        model.ingest(_fb("INC-001", FeedbackKind.APPROVAL))
        model.ingest(_fb("INC-002", FeedbackKind.APPROVAL))
        model.ingest(_fb("INC-003", FeedbackKind.REJECTION))
        profile = model.operator_profile_for_mechanism("ops-1", "memory_pressure")
        assert profile.agreement_rate == pytest.approx(2 / 3, abs=0.01)

    def test_most_common_correction_kind(self):
        model = OperatorTrustModel()
        model.ingest(_fb("INC-001", FeedbackKind.ROLLBACK))
        model.ingest(_fb("INC-002", FeedbackKind.ROLLBACK))
        model.ingest(_fb("INC-003", FeedbackKind.REJECTION))
        profile = model.operator_profile_for_mechanism("ops-1", "memory_pressure")
        assert profile.most_common_correction_kind == "rollback"

    def test_remediation_consensus_empty(self):
        model = OperatorTrustModel()
        profile = model.remediation_consensus("scale_replicas")
        assert profile.total_interactions == 0
        assert profile.consensus_trust_score == 0.5

    def test_remediation_consensus_all_approvals(self):
        model = OperatorTrustModel()
        for i in range(5):
            model.ingest(_fb(f"INC-{i:03d}", FeedbackKind.APPROVAL))
        profile = model.remediation_consensus("scale_replicas")
        assert profile.consensus_trust_score == 1.0

    def test_remediation_controversial_flag(self):
        model = OperatorTrustModel()
        for i in range(3):
            model.ingest(_fb(f"INC-A{i}", FeedbackKind.APPROVAL))
        for i in range(3):
            model.ingest(_fb(f"INC-B{i}", FeedbackKind.REJECTION))
        profile = model.remediation_consensus("scale_replicas")
        assert profile.controversial is True

    def test_remediation_not_controversial_when_all_approve(self):
        model = OperatorTrustModel()
        for i in range(5):
            model.ingest(_fb(f"INC-{i:03d}", FeedbackKind.APPROVAL))
        profile = model.remediation_consensus("scale_replicas")
        assert profile.controversial is False

    def test_operators_who_challenged_mechanism(self):
        model = OperatorTrustModel()
        model.ingest(_fb("INC-001", FeedbackKind.REJECTION, operator_id="ops-1"))
        model.ingest(_fb("INC-002", FeedbackKind.APPROVAL, operator_id="ops-2"))
        challengers = model.operators_who_challenged_mechanism("memory_pressure")
        assert "ops-1" in challengers
        assert "ops-2" not in challengers

    def test_most_challenged_mechanisms(self):
        model = OperatorTrustModel()
        for i in range(3):
            model.ingest(_fb(f"INC-A{i}", FeedbackKind.REJECTION, mechanism_id="retry_storm"))
        for i in range(1):
            model.ingest(_fb(f"INC-B{i}", FeedbackKind.REJECTION, mechanism_id="memory_pressure"))
        top = model.most_challenged_mechanisms(top_n=2)
        assert top[0][0] == "retry_storm"

    def test_operator_agreement_rate_insufficient_data(self):
        model = OperatorTrustModel()
        model.ingest(_fb("INC-001", FeedbackKind.APPROVAL))
        rate = model.operator_agreement_rate("ops-1")
        assert rate == 0.5  # fewer than 3 interactions → neutral

    def test_operator_agreement_rate_computed(self):
        model = OperatorTrustModel()
        for i in range(3):
            model.ingest(_fb(f"INC-{i:03d}", FeedbackKind.APPROVAL))
        for i in range(3, 6):
            model.ingest(_fb(f"INC-{i:03d}", FeedbackKind.REJECTION))
        rate = model.operator_agreement_rate("ops-1")
        assert rate == pytest.approx(0.5, abs=0.01)

    def test_ingest_batch(self):
        model = OperatorTrustModel()
        records = [_fb(f"INC-{i:03d}", FeedbackKind.APPROVAL) for i in range(5)]
        model.ingest_batch(records)
        profile = model.operator_profile_for_mechanism("ops-1", "memory_pressure")
        assert profile.total_interactions == 5

    def test_most_controversial_remediations(self):
        model = OperatorTrustModel()
        # Make scale_replicas controversial
        for i in range(2):
            model.ingest(
                _fb(f"INC-A{i}", FeedbackKind.APPROVAL, remediation_class="scale_replicas")
            )
        for i in range(2):
            model.ingest(
                _fb(f"INC-B{i}", FeedbackKind.REJECTION, remediation_class="scale_replicas")
            )
        # Make flush_cache non-controversial
        for i in range(5):
            model.ingest(_fb(f"INC-C{i}", FeedbackKind.APPROVAL, remediation_class="flush_cache"))
        controversial = model.most_controversial_remediations(top_n=5)
        classes = [cls for cls, _ in controversial]
        # scale_replicas has 50/50 → more controversial than flush_cache
        assert "scale_replicas" in classes
