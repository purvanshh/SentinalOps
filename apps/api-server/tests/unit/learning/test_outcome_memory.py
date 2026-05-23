"""Tests for ExecutionOutcomeMemory (Phase 46)."""

from __future__ import annotations

import pytest
from learning.outcome_memory import (
    ExecutionOutcomeMemory,
    OutcomeRecord,
)


def _success_record(
    outcome_id: str = "OUT-001",
    incident_id: str = "INC-001",
    remediation_class: str = "scale_replicas",
    mechanism_id: str = "memory_pressure",
) -> OutcomeRecord:
    return OutcomeRecord(
        outcome_id=outcome_id,
        incident_id=incident_id,
        remediation_class=remediation_class,
        mechanism_id=mechanism_id,
        incident_category="performance",
        success=True,
    )


def _harmful_record(
    outcome_id: str = "OUT-002",
    incident_id: str = "INC-002",
    remediation_class: str = "increase_pool_size",
    mechanism_id: str = "connection_pool_starvation",
) -> OutcomeRecord:
    return OutcomeRecord(
        outcome_id=outcome_id,
        incident_id=incident_id,
        remediation_class=remediation_class,
        mechanism_id=mechanism_id,
        incident_category="availability",
        success=False,
        required_rollback=True,
    )


def _failure_record(
    outcome_id: str = "OUT-003",
    incident_id: str = "INC-003",
    remediation_class: str = "flush_cache",
    mechanism_id: str = "stale_cache_poisoning",
) -> OutcomeRecord:
    return OutcomeRecord(
        outcome_id=outcome_id,
        incident_id=incident_id,
        remediation_class=remediation_class,
        mechanism_id=mechanism_id,
        incident_category="performance",
        success=False,
    )


class TestOutcomeRecord:
    def test_success_effectiveness_is_one(self):
        rec = _success_record()
        assert rec.effectiveness_score == 1.0

    def test_harmful_effectiveness_is_zero(self):
        rec = _harmful_record()
        assert rec.effectiveness_score == 0.0

    def test_failure_effectiveness_is_low(self):
        rec = _failure_record()
        assert rec.effectiveness_score == 0.25

    def test_postmortem_correction_reduces_score(self):
        rec = OutcomeRecord(
            outcome_id="OUT-004",
            incident_id="INC-004",
            remediation_class="scale_replicas",
            mechanism_id="memory_pressure",
            incident_category="performance",
            success=True,
            postmortem_correction=True,
        )
        assert rec.effectiveness_score == 0.60

    def test_escalation_effectiveness(self):
        rec = OutcomeRecord(
            outcome_id="OUT-005",
            incident_id="INC-005",
            remediation_class="scale_replicas",
            mechanism_id="memory_pressure",
            incident_category="performance",
            success=True,
            escalation_was_necessary=True,
        )
        assert rec.effectiveness_score == 0.70

    def test_operator_reversal_makes_harmful(self):
        rec = OutcomeRecord(
            outcome_id="OUT-006",
            incident_id="INC-006",
            remediation_class="flush_cache",
            mechanism_id=None,
            incident_category="performance",
            success=False,
            operator_reversal=True,
        )
        assert rec.was_harmful is True
        assert rec.effectiveness_score == 0.0

    def test_to_dict_keys(self):
        d = _success_record().to_dict()
        for key in [
            "outcome_id",
            "incident_id",
            "remediation_class",
            "success",
            "effectiveness_score",
            "was_harmful",
        ]:
            assert key in d


class TestExecutionOutcomeMemory:
    def test_store_and_retrieve(self):
        mem = ExecutionOutcomeMemory()
        mem.store(_success_record())
        assert len(mem.all_records()) == 1

    def test_records_for_remediation(self):
        mem = ExecutionOutcomeMemory()
        mem.store(_success_record(remediation_class="scale_replicas"))
        mem.store(_harmful_record(remediation_class="increase_pool_size"))
        assert len(mem.records_for_remediation("scale_replicas")) == 1
        assert len(mem.records_for_remediation("increase_pool_size")) == 1
        assert len(mem.records_for_remediation("unknown")) == 0

    def test_reliability_profile_empty(self):
        mem = ExecutionOutcomeMemory()
        profile = mem.reliability_for_remediation("scale_replicas")
        assert profile.total_executions == 0
        assert profile.sample_size_warning is True
        assert profile.success_rate == 0.5  # neutral prior

    def test_reliability_profile_all_success(self):
        mem = ExecutionOutcomeMemory()
        for i in range(5):
            mem.store(_success_record(outcome_id=f"OUT-{i:03d}", incident_id=f"INC-{i:03d}"))
        profile = mem.reliability_for_remediation("scale_replicas")
        assert profile.success_rate == 1.0
        assert profile.harm_rate == 0.0
        assert profile.sample_size_warning is False

    def test_reliability_profile_with_rollbacks(self):
        mem = ExecutionOutcomeMemory()
        for i in range(3):
            mem.store(_success_record(outcome_id=f"OUT-S{i}", incident_id=f"INC-S{i}"))
        for i in range(2):
            mem.store(
                _harmful_record(
                    outcome_id=f"OUT-H{i}",
                    incident_id=f"INC-H{i}",
                    remediation_class="scale_replicas",
                    mechanism_id="memory_pressure",
                )
            )
        profile = mem.reliability_for_remediation("scale_replicas")
        assert profile.rollback_count == 2
        assert profile.harm_rate == pytest.approx(0.4, abs=0.01)

    def test_rollback_rate_for_remediation(self):
        mem = ExecutionOutcomeMemory()
        mem.store(_success_record())
        mem.store(
            _harmful_record(
                outcome_id="OUT-H1",
                incident_id="INC-H1",
                remediation_class="scale_replicas",
                mechanism_id="memory_pressure",
            )
        )
        rate = mem.rollback_rate_for_remediation("scale_replicas")
        assert rate == pytest.approx(0.5, abs=0.01)

    def test_rollback_rate_no_records_is_zero(self):
        mem = ExecutionOutcomeMemory()
        assert mem.rollback_rate_for_remediation("nonexistent") == 0.0

    def test_mean_effectiveness_for_mechanism_remediation(self):
        mem = ExecutionOutcomeMemory()
        mem.store(_success_record())
        mem.store(
            _failure_record(
                outcome_id="OUT-F1",
                incident_id="INC-F1",
                remediation_class="scale_replicas",
                mechanism_id="memory_pressure",
            )
        )
        eff = mem.mean_effectiveness_for_mechanism_remediation("memory_pressure", "scale_replicas")
        assert eff == pytest.approx((1.0 + 0.25) / 2, abs=0.01)

    def test_mean_effectiveness_unknown_returns_neutral(self):
        mem = ExecutionOutcomeMemory()
        eff = mem.mean_effectiveness_for_mechanism_remediation("unknown", "unknown")
        assert eff == 0.5

    def test_most_harmful_remediations(self):
        mem = ExecutionOutcomeMemory()
        mem.store(_harmful_record())
        mem.store(
            _harmful_record(
                outcome_id="OUT-H2",
                incident_id="INC-H2",
                remediation_class="increase_pool_size",
                mechanism_id="connection_pool_starvation",
            )
        )
        mem.store(_success_record())
        harmful = mem.most_harmful_remediations(top_n=3)
        assert any(cls == "increase_pool_size" for cls, _ in harmful)

    def test_blast_radius_accuracy_no_records(self):
        mem = ExecutionOutcomeMemory()
        assert mem.blast_radius_accuracy() == 1.0

    def test_blast_radius_accuracy_within_tolerance(self):
        mem = ExecutionOutcomeMemory()
        rec = OutcomeRecord(
            outcome_id="OUT-BR",
            incident_id="INC-BR",
            remediation_class="scale_replicas",
            mechanism_id=None,
            incident_category="performance",
            success=True,
            predicted_blast_radius=10,
            actual_blast_radius=12,  # 20% off — within 50% tolerance
        )
        mem.store(rec)
        assert mem.blast_radius_accuracy() == 1.0

    def test_blast_radius_accuracy_outside_tolerance(self):
        mem = ExecutionOutcomeMemory()
        rec = OutcomeRecord(
            outcome_id="OUT-BR2",
            incident_id="INC-BR2",
            remediation_class="scale_replicas",
            mechanism_id=None,
            incident_category="performance",
            success=True,
            predicted_blast_radius=1,
            actual_blast_radius=10,  # 900% off
        )
        mem.store(rec)
        assert mem.blast_radius_accuracy() == 0.0

    def test_records_for_mechanism(self):
        mem = ExecutionOutcomeMemory()
        mem.store(_success_record(mechanism_id="memory_pressure"))
        mem.store(_failure_record(mechanism_id="stale_cache_poisoning"))
        assert len(mem.records_for_mechanism("memory_pressure")) == 1
        assert len(mem.records_for_mechanism("stale_cache_poisoning")) == 1
