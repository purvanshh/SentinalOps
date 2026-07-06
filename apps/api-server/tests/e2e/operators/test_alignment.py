"""
Tests for Phase 49 Commit 5 — operator alignment benchmarking and trust
realism scoring:
  - OperatorAlignmentBenchmark  (operator_alignment.py)
  - TrustRealismModel           (trust_realism.py)
  - DisagreementAnalyzer        (disagreement_analysis.py)
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

import pytest
from operators.workflow.disagreement_analysis import (
    DisagreementAnalysisReport,
    DisagreementAnalyzer,
    DisagreementKind,
    DisagreementPattern,
    DisagreementRecord,
)
from operators.workflow.operator_alignment import (
    AlignmentBand,
    AlignmentMetrics,
    OperatorAlignmentBenchmark,
    OperatorAlignmentReport,
)
from operators.workflow.trust_realism import (
    TrustEvent,
    TrustRealismModel,
    TrustRealismScore,
)

# ===========================================================================
# Helpers
# ===========================================================================


def _bench() -> OperatorAlignmentBenchmark:
    return OperatorAlignmentBenchmark()


def _trust() -> TrustRealismModel:
    return TrustRealismModel()


def _rec(
    operator_id: str = "op-1",
    incident_id: str = "inc-1",
    kind: DisagreementKind = DisagreementKind.OVERRIDE,
    has_justification: bool = True,
) -> DisagreementRecord:
    return DisagreementRecord(
        operator_id=operator_id,
        incident_id=incident_id,
        kind=kind,
        recommendation_summary="Restart the api deployment.",
        operator_action="Did nothing.",
        rationale="Operator rationale here.",
        has_justification=has_justification,
    )


# ===========================================================================
# OperatorAlignmentBenchmark
# ===========================================================================


class TestOperatorAlignmentBenchmark:
    # ---- Return type -------------------------------------------------------

    def test_returns_operator_alignment_report(self) -> None:
        report = _bench().benchmark(
            operator_id="op-1",
            recommendations_reviewed=10,
            accepted=8,
            overrides_total=2,
            justified_overrides=1,
            delayed_overrides=1,
            escalations_total=5,
            correct_escalations=4,
            remediations_total=6,
            rollbacks_triggered=1,
        )
        assert isinstance(report, OperatorAlignmentReport)

    def test_report_contains_alignment_metrics(self) -> None:
        report = _bench().benchmark(
            operator_id="op-2",
            recommendations_reviewed=20,
            accepted=15,
            overrides_total=5,
            justified_overrides=3,
            delayed_overrides=2,
            escalations_total=8,
            correct_escalations=6,
            remediations_total=10,
            rollbacks_triggered=2,
        )
        assert isinstance(report.metrics, AlignmentMetrics)

    def test_operator_id_propagated(self) -> None:
        report = _bench().benchmark(
            operator_id="op-unique",
            recommendations_reviewed=5,
            accepted=5,
            overrides_total=0,
            justified_overrides=0,
            delayed_overrides=0,
            escalations_total=2,
            correct_escalations=2,
            remediations_total=3,
            rollbacks_triggered=0,
        )
        assert report.operator_id == "op-unique"
        assert report.metrics.operator_id == "op-unique"

    # ---- Metric calculation ------------------------------------------------

    def test_acceptance_rate_calculation(self) -> None:
        report = _bench().benchmark(
            operator_id="op-3",
            recommendations_reviewed=10,
            accepted=7,
            overrides_total=3,
            justified_overrides=2,
            delayed_overrides=1,
            escalations_total=4,
            correct_escalations=3,
            remediations_total=5,
            rollbacks_triggered=1,
        )
        assert report.metrics.recommendation_acceptance_rate == pytest.approx(7 / 10)

    def test_justified_override_rate_calculation(self) -> None:
        report = _bench().benchmark(
            operator_id="op-4",
            recommendations_reviewed=10,
            accepted=7,
            overrides_total=6,
            justified_overrides=3,
            delayed_overrides=2,
            escalations_total=4,
            correct_escalations=3,
            remediations_total=5,
            rollbacks_triggered=1,
        )
        assert report.metrics.justified_override_rate == pytest.approx(3 / 6)

    def test_disagreement_rate_calculation(self) -> None:
        report = _bench().benchmark(
            operator_id="op-5",
            recommendations_reviewed=10,
            accepted=6,
            overrides_total=4,
            justified_overrides=2,
            delayed_overrides=1,
            escalations_total=3,
            correct_escalations=2,
            remediations_total=4,
            rollbacks_triggered=1,
        )
        # 4 rejections / 10 total
        assert report.metrics.operator_disagreement_rate == pytest.approx(4 / 10)

    def test_delayed_override_rate_calculation(self) -> None:
        report = _bench().benchmark(
            operator_id="op-6",
            recommendations_reviewed=10,
            accepted=7,
            overrides_total=4,
            justified_overrides=2,
            delayed_overrides=2,
            escalations_total=3,
            correct_escalations=2,
            remediations_total=4,
            rollbacks_triggered=0,
        )
        assert report.metrics.delayed_override_rate == pytest.approx(2 / 4)

    def test_escalation_accuracy_calculation(self) -> None:
        report = _bench().benchmark(
            operator_id="op-7",
            recommendations_reviewed=10,
            accepted=8,
            overrides_total=2,
            justified_overrides=1,
            delayed_overrides=0,
            escalations_total=5,
            correct_escalations=4,
            remediations_total=5,
            rollbacks_triggered=0,
        )
        assert report.metrics.escalation_accuracy == pytest.approx(4 / 5)

    def test_remediation_regret_rate_calculation(self) -> None:
        report = _bench().benchmark(
            operator_id="op-8",
            recommendations_reviewed=10,
            accepted=8,
            overrides_total=2,
            justified_overrides=1,
            delayed_overrides=0,
            escalations_total=5,
            correct_escalations=4,
            remediations_total=8,
            rollbacks_triggered=2,
        )
        assert report.metrics.remediation_regret_rate == pytest.approx(2 / 8)

    def test_remediation_regret_count_in_report(self) -> None:
        report = _bench().benchmark(
            operator_id="op-9",
            recommendations_reviewed=10,
            accepted=8,
            overrides_total=2,
            justified_overrides=1,
            delayed_overrides=0,
            escalations_total=5,
            correct_escalations=4,
            remediations_total=8,
            rollbacks_triggered=3,
        )
        assert report.remediation_regret_count == 3

    def test_recommendations_reviewed_in_report(self) -> None:
        report = _bench().benchmark(
            operator_id="op-10",
            recommendations_reviewed=42,
            accepted=40,
            overrides_total=2,
            justified_overrides=2,
            delayed_overrides=0,
            escalations_total=5,
            correct_escalations=5,
            remediations_total=5,
            rollbacks_triggered=0,
        )
        assert report.recommendations_reviewed == 42

    def test_overrides_total_in_report(self) -> None:
        report = _bench().benchmark(
            operator_id="op-11",
            recommendations_reviewed=10,
            accepted=7,
            overrides_total=7,
            justified_overrides=5,
            delayed_overrides=2,
            escalations_total=3,
            correct_escalations=2,
            remediations_total=4,
            rollbacks_triggered=1,
        )
        assert report.overrides_total == 7

    # ---- Alignment score formula -------------------------------------------

    def test_alignment_score_formula_perfect_operator(self) -> None:
        # All metrics at best values WITH overrides, so justified_override_rate=1.0:
        # acceptance=1.0, disagreement=0.0, escalation=1.0, regret=0.0, justified=1.0
        # 0.30*1 + 0.20*(1-0) + 0.20*1 + 0.15*(1-0) + 0.15*1 = 1.0
        report = _bench().benchmark(
            operator_id="op-perfect",
            recommendations_reviewed=10,
            accepted=10,
            overrides_total=4,  # 4 overrides, all justified
            justified_overrides=4,
            delayed_overrides=0,
            escalations_total=5,
            correct_escalations=5,
            remediations_total=5,
            rollbacks_triggered=0,
        )
        assert report.alignment_score == pytest.approx(1.0, abs=0.01)

    def test_alignment_score_formula_worst_case(self) -> None:
        # acceptance=0, disagreement=1, escalation=0, regret=1, justified=0
        # 0.30*0 + 0.20*0 + 0.20*0 + 0.15*0 + 0.15*0 = 0.0
        report = _bench().benchmark(
            operator_id="op-worst",
            recommendations_reviewed=10,
            accepted=0,
            overrides_total=10,
            justified_overrides=0,
            delayed_overrides=10,
            escalations_total=5,
            correct_escalations=0,
            remediations_total=5,
            rollbacks_triggered=5,
        )
        assert report.alignment_score == pytest.approx(0.0, abs=0.01)

    def test_alignment_score_bounded_0_to_1(self) -> None:
        for accepted in [0, 5, 10]:
            report = _bench().benchmark(
                operator_id=f"op-b{accepted}",
                recommendations_reviewed=10,
                accepted=accepted,
                overrides_total=5,
                justified_overrides=3,
                delayed_overrides=1,
                escalations_total=4,
                correct_escalations=2,
                remediations_total=6,
                rollbacks_triggered=2,
            )
            assert 0.0 <= report.alignment_score <= 1.0

    def test_alignment_score_partial_case(self) -> None:
        # acceptance=0.8, disagreement=0.2, escalation=0.8, regret=0.2, justified=0.5
        # 0.30*0.8 + 0.20*(0.8) + 0.20*0.8 + 0.15*0.8 + 0.15*0.5
        # = 0.24 + 0.16 + 0.16 + 0.12 + 0.075 = 0.755
        report = _bench().benchmark(
            operator_id="op-partial",
            recommendations_reviewed=10,
            accepted=8,
            overrides_total=2,
            justified_overrides=1,
            delayed_overrides=0,
            escalations_total=5,
            correct_escalations=4,
            remediations_total=5,
            rollbacks_triggered=1,
        )
        assert report.alignment_score == pytest.approx(0.755, abs=0.01)

    # ---- Band classification -----------------------------------------------

    def test_band_well_aligned_at_075(self) -> None:
        report = _bench().benchmark(
            operator_id="op-wa",
            recommendations_reviewed=10,
            accepted=10,
            overrides_total=0,
            justified_overrides=0,
            delayed_overrides=0,
            escalations_total=5,
            correct_escalations=5,
            remediations_total=5,
            rollbacks_triggered=0,
        )
        assert report.alignment_band == AlignmentBand.WELL_ALIGNED

    def test_band_generally_aligned_at_055_to_075(self) -> None:
        # score ≈ 0.60 → GENERALLY_ALIGNED
        # acceptance=0.5, disagreement=0.5, escalation=0.5, regret=0.5, justified=0.5
        # 0.30*0.5 + 0.20*0.5 + 0.20*0.5 + 0.15*0.5 + 0.15*0.5 = 0.50
        # Tune: acceptance=0.7, disagreement=0.3, escalation=0.7, regret=0.3, justified=0.7
        # 0.21 + 0.14 + 0.14 + 0.105 + 0.105 = 0.70 → GENERALLY_ALIGNED
        report = _bench().benchmark(
            operator_id="op-ga",
            recommendations_reviewed=10,
            accepted=7,
            overrides_total=10,
            justified_overrides=7,
            delayed_overrides=0,
            escalations_total=10,
            correct_escalations=7,
            remediations_total=10,
            rollbacks_triggered=3,
        )
        assert report.alignment_band == AlignmentBand.GENERALLY_ALIGNED

    def test_band_misaligned_at_035_to_055(self) -> None:
        # Need score in [0.35, 0.55)
        # acceptance=0.4, disagreement=0.6, escalation=0.4, regret=0.6, justified=0.4
        # 0.12 + 0.08 + 0.08 + 0.06 + 0.06 = 0.40 → MISALIGNED
        report = _bench().benchmark(
            operator_id="op-ma",
            recommendations_reviewed=10,
            accepted=4,
            overrides_total=10,
            justified_overrides=4,
            delayed_overrides=0,
            escalations_total=10,
            correct_escalations=4,
            remediations_total=10,
            rollbacks_triggered=6,
        )
        assert report.alignment_band == AlignmentBand.MISALIGNED

    def test_band_adversarial_below_035(self) -> None:
        report = _bench().benchmark(
            operator_id="op-adv",
            recommendations_reviewed=10,
            accepted=0,
            overrides_total=10,
            justified_overrides=0,
            delayed_overrides=10,
            escalations_total=5,
            correct_escalations=0,
            remediations_total=5,
            rollbacks_triggered=5,
        )
        assert report.alignment_band == AlignmentBand.ADVERSARIAL

    def test_band_enum_type(self) -> None:
        report = _bench().benchmark(
            operator_id="op-enum",
            recommendations_reviewed=5,
            accepted=5,
            overrides_total=0,
            justified_overrides=0,
            delayed_overrides=0,
            escalations_total=2,
            correct_escalations=2,
            remediations_total=2,
            rollbacks_triggered=0,
        )
        assert isinstance(report.alignment_band, AlignmentBand)

    # ---- Division-by-zero guards -------------------------------------------

    def test_zero_recommendations_no_crash(self) -> None:
        report = _bench().benchmark(
            operator_id="op-zero",
            recommendations_reviewed=0,
            accepted=0,
            overrides_total=0,
            justified_overrides=0,
            delayed_overrides=0,
            escalations_total=0,
            correct_escalations=0,
            remediations_total=0,
            rollbacks_triggered=0,
        )
        # max(0,1) denominators → all rates = 0 or 1 depending on numerator
        assert 0.0 <= report.alignment_score <= 1.0

    def test_zero_overrides_no_crash(self) -> None:
        report = _bench().benchmark(
            operator_id="op-no-overrides",
            recommendations_reviewed=10,
            accepted=10,
            overrides_total=0,
            justified_overrides=0,
            delayed_overrides=0,
            escalations_total=5,
            correct_escalations=5,
            remediations_total=5,
            rollbacks_triggered=0,
        )
        assert report.metrics.justified_override_rate == pytest.approx(0.0)
        assert report.metrics.delayed_override_rate == pytest.approx(0.0)

    def test_zero_escalations_no_crash(self) -> None:
        report = _bench().benchmark(
            operator_id="op-no-esc",
            recommendations_reviewed=10,
            accepted=8,
            overrides_total=2,
            justified_overrides=1,
            delayed_overrides=0,
            escalations_total=0,
            correct_escalations=0,
            remediations_total=5,
            rollbacks_triggered=1,
        )
        assert report.metrics.escalation_accuracy == pytest.approx(0.0)

    def test_zero_remediations_no_crash(self) -> None:
        report = _bench().benchmark(
            operator_id="op-no-rem",
            recommendations_reviewed=10,
            accepted=8,
            overrides_total=2,
            justified_overrides=1,
            delayed_overrides=0,
            escalations_total=3,
            correct_escalations=2,
            remediations_total=0,
            rollbacks_triggered=0,
        )
        assert report.metrics.remediation_regret_rate == pytest.approx(0.0)


# ===========================================================================
# TrustRealismModel
# ===========================================================================


class TestTrustRealismModel:
    # ---- Initial state -------------------------------------------------------

    def test_initial_trust_is_0_60(self) -> None:
        model = _trust()
        score = model.get_score("op-new")
        assert score.current_trust == pytest.approx(0.60)

    def test_get_score_returns_trust_realism_score(self) -> None:
        model = _trust()
        score = model.get_score("op-new")
        assert isinstance(score, TrustRealismScore)

    def test_initial_trust_events_empty(self) -> None:
        model = _trust()
        score = model.get_score("op-new")
        assert score.trust_events == []

    def test_initial_cumulative_fields_are_zero(self) -> None:
        model = _trust()
        score = model.get_score("op-new")
        assert score.trust_earned_from_outcomes == pytest.approx(0.0)
        assert score.distrust_from_false_certainty == pytest.approx(0.0)
        assert score.distrust_from_escalation_spam == pytest.approx(0.0)
        assert score.distrust_from_rollbacks == pytest.approx(0.0)
        assert score.distrust_from_vague_recommendations == pytest.approx(0.0)

    # ---- CRITICAL INVARIANT: distrust > trust gains -------------------------

    def test_rollback_penalty_greater_than_positive_gain(self) -> None:
        """rollback_loop (0.10) must exceed positive_outcome (0.03)."""
        from operators.workflow.trust_realism import _INITIAL_TRUST

        model_pos = _trust()
        model_neg = _trust()
        model_pos.record_positive_outcome("op-a")
        model_neg.record_rollback_loop("op-b")
        pos_delta = model_pos.get_score("op-a").current_trust - _INITIAL_TRUST
        neg_delta = _INITIAL_TRUST - model_neg.get_score("op-b").current_trust
        assert neg_delta > pos_delta

    def test_false_certainty_penalty_greater_than_positive_gain(self) -> None:
        from operators.workflow.trust_realism import _INITIAL_TRUST

        model_pos = _trust()
        model_neg = _trust()
        model_pos.record_positive_outcome("op-a")
        model_neg.record_false_certainty("op-b")
        pos_delta = model_pos.get_score("op-a").current_trust - _INITIAL_TRUST
        neg_delta = _INITIAL_TRUST - model_neg.get_score("op-b").current_trust
        assert neg_delta > pos_delta

    def test_escalation_spam_penalty_greater_than_positive_gain(self) -> None:
        from operators.workflow.trust_realism import _INITIAL_TRUST

        model_pos = _trust()
        model_neg = _trust()
        model_pos.record_positive_outcome("op-a")
        model_neg.record_escalation_spam("op-b")
        pos_delta = model_pos.get_score("op-a").current_trust - _INITIAL_TRUST
        neg_delta = _INITIAL_TRUST - model_neg.get_score("op-b").current_trust
        assert neg_delta > pos_delta

    def test_vague_recommendation_penalty_greater_than_positive_gain(self) -> None:
        from operators.workflow.trust_realism import _INITIAL_TRUST

        model_pos = _trust()
        model_neg = _trust()
        model_pos.record_positive_outcome("op-a")
        model_neg.record_vague_recommendation("op-b")
        pos_delta = model_pos.get_score("op-a").current_trust - _INITIAL_TRUST
        neg_delta = _INITIAL_TRUST - model_neg.get_score("op-b").current_trust
        assert neg_delta > pos_delta

    def test_rollback_is_highest_penalty(self) -> None:
        """rollback_loop (0.10) is the largest single penalty."""
        from operators.workflow.trust_realism import _INITIAL_TRUST

        penalties = {}
        for name, method in [
            ("false_certainty", "record_false_certainty"),
            ("escalation_spam", "record_escalation_spam"),
            ("rollback_loop", "record_rollback_loop"),
            ("vague_rec", "record_vague_recommendation"),
        ]:
            m = _trust()
            getattr(m, method)("op-x")
            penalties[name] = _INITIAL_TRUST - m.get_score("op-x").current_trust
        assert penalties["rollback_loop"] == max(penalties.values())

    # ---- Trust floor / ceiling ---------------------------------------------

    def test_trust_ceiling_enforced_at_090(self) -> None:
        model = _trust()
        # Apply many positive outcomes; trust must never exceed 0.90
        for _ in range(100):
            model.record_positive_outcome("op-ceil")
        score = model.get_score("op-ceil")
        assert score.current_trust <= 0.90

    def test_trust_floor_enforced_at_005(self) -> None:
        model = _trust()
        # Apply many rollbacks; trust must never drop below 0.05
        for _ in range(100):
            model.record_rollback_loop("op-floor")
        score = model.get_score("op-floor")
        assert score.current_trust >= 0.05

    def test_trust_stays_within_bounds_after_mixed_events(self) -> None:
        model = _trust()
        for _ in range(20):
            model.record_positive_outcome("op-m")
            model.record_false_certainty("op-m")
            model.record_rollback_loop("op-m")
        score = model.get_score("op-m")
        assert 0.05 <= score.current_trust <= 0.90

    # ---- Each event type returns TrustEvent --------------------------------

    def test_positive_outcome_returns_trust_event(self) -> None:
        model = _trust()
        event = model.record_positive_outcome("op-e1")
        assert isinstance(event, TrustEvent)
        assert event.is_distrust is False
        assert event.trust_delta > 0.0

    def test_false_certainty_returns_trust_event(self) -> None:
        model = _trust()
        event = model.record_false_certainty("op-e2")
        assert isinstance(event, TrustEvent)
        assert event.is_distrust is True
        assert event.trust_delta < 0.0

    def test_escalation_spam_returns_trust_event(self) -> None:
        model = _trust()
        event = model.record_escalation_spam("op-e3")
        assert isinstance(event, TrustEvent)
        assert event.is_distrust is True
        assert event.trust_delta < 0.0

    def test_rollback_loop_returns_trust_event(self) -> None:
        model = _trust()
        event = model.record_rollback_loop("op-e4")
        assert isinstance(event, TrustEvent)
        assert event.is_distrust is True
        assert event.trust_delta < 0.0

    def test_vague_recommendation_returns_trust_event(self) -> None:
        model = _trust()
        event = model.record_vague_recommendation("op-e5")
        assert isinstance(event, TrustEvent)
        assert event.is_distrust is True
        assert event.trust_delta < 0.0

    # ---- Cumulative accounting ---------------------------------------------

    def test_trust_earned_from_outcomes_accumulates(self) -> None:
        model = _trust()
        model.record_positive_outcome("op-acc", magnitude=0.03)
        model.record_positive_outcome("op-acc", magnitude=0.03)
        score = model.get_score("op-acc")
        assert score.trust_earned_from_outcomes == pytest.approx(0.06)

    def test_distrust_from_false_certainty_accumulates(self) -> None:
        model = _trust()
        model.record_false_certainty("op-acc2", magnitude=0.08)
        model.record_false_certainty("op-acc2", magnitude=0.08)
        score = model.get_score("op-acc2")
        assert score.distrust_from_false_certainty == pytest.approx(0.16)

    def test_distrust_from_escalation_spam_accumulates(self) -> None:
        model = _trust()
        model.record_escalation_spam("op-acc3", magnitude=0.06)
        score = model.get_score("op-acc3")
        assert score.distrust_from_escalation_spam == pytest.approx(0.06)

    def test_distrust_from_rollbacks_accumulates(self) -> None:
        model = _trust()
        model.record_rollback_loop("op-acc4", magnitude=0.10)
        score = model.get_score("op-acc4")
        assert score.distrust_from_rollbacks == pytest.approx(0.10)

    def test_distrust_from_vague_recommendations_accumulates(self) -> None:
        model = _trust()
        model.record_vague_recommendation("op-acc5", magnitude=0.05)
        score = model.get_score("op-acc5")
        assert score.distrust_from_vague_recommendations == pytest.approx(0.05)

    def test_net_trust_change_computed_correctly(self) -> None:
        model = _trust()
        model.record_positive_outcome("op-net", magnitude=0.03)
        model.record_rollback_loop("op-net", magnitude=0.10)
        score = model.get_score("op-net")
        expected_net = score.trust_earned_from_outcomes - (
            score.distrust_from_false_certainty
            + score.distrust_from_escalation_spam
            + score.distrust_from_rollbacks
            + score.distrust_from_vague_recommendations
        )
        assert score.net_trust_change == pytest.approx(expected_net)

    def test_trust_events_list_grows_with_each_event(self) -> None:
        model = _trust()
        model.record_positive_outcome("op-list")
        model.record_rollback_loop("op-list")
        model.record_vague_recommendation("op-list")
        score = model.get_score("op-list")
        assert len(score.trust_events) == 3

    def test_separate_operators_are_independent(self) -> None:
        model = _trust()
        model.record_rollback_loop("op-A")
        model.record_rollback_loop("op-A")
        # op-B should be untouched
        score_b = model.get_score("op-B")
        assert score_b.current_trust == pytest.approx(0.60)
        assert score_b.distrust_from_rollbacks == pytest.approx(0.0)

    def test_operator_id_propagated_in_score(self) -> None:
        model = _trust()
        score = model.get_score("op-id-check")
        assert score.operator_id == "op-id-check"

    # ---- Event type labels -------------------------------------------------

    def test_positive_outcome_event_type_label(self) -> None:
        model = _trust()
        event = model.record_positive_outcome("op-label")
        assert event.event_type == "POSITIVE_OUTCOME"

    def test_false_certainty_event_type_label(self) -> None:
        model = _trust()
        event = model.record_false_certainty("op-label2")
        assert event.event_type == "FALSE_CERTAINTY"

    def test_escalation_spam_event_type_label(self) -> None:
        model = _trust()
        event = model.record_escalation_spam("op-label3")
        assert event.event_type == "ESCALATION_SPAM"

    def test_rollback_loop_event_type_label(self) -> None:
        model = _trust()
        event = model.record_rollback_loop("op-label4")
        assert event.event_type == "ROLLBACK_LOOP"

    def test_vague_recommendation_event_type_label(self) -> None:
        model = _trust()
        event = model.record_vague_recommendation("op-label5")
        assert event.event_type == "VAGUE_RECOMMENDATION"


# ===========================================================================
# DisagreementAnalyzer
# ===========================================================================


class TestDisagreementAnalyzer:
    # ---- Empty state -------------------------------------------------------

    def test_empty_analyze_returns_report(self) -> None:
        analyzer = DisagreementAnalyzer()
        report = analyzer.analyze()
        assert isinstance(report, DisagreementAnalysisReport)

    def test_empty_total_disagreements_zero(self) -> None:
        analyzer = DisagreementAnalyzer()
        report = analyzer.analyze()
        assert report.total_disagreements == 0

    def test_empty_by_kind_all_zero(self) -> None:
        analyzer = DisagreementAnalyzer()
        report = analyzer.analyze()
        for kind in DisagreementKind:
            assert report.by_kind[kind.value] == 0

    def test_empty_no_systematic_rejection(self) -> None:
        analyzer = DisagreementAnalyzer()
        report = analyzer.analyze()
        assert report.systematic_rejection_detected is False

    def test_empty_no_silent_bypass(self) -> None:
        analyzer = DisagreementAnalyzer()
        report = analyzer.analyze()
        assert report.silent_bypass_detected is False

    def test_empty_unjustified_override_count_zero(self) -> None:
        analyzer = DisagreementAnalyzer()
        report = analyzer.analyze()
        assert report.unjustified_override_count == 0

    # ---- record() and total count ------------------------------------------

    def test_single_record_total_is_1(self) -> None:
        analyzer = DisagreementAnalyzer()
        analyzer.record(_rec())
        report = analyzer.analyze()
        assert report.total_disagreements == 1

    def test_multiple_records_total_correct(self) -> None:
        analyzer = DisagreementAnalyzer()
        for i in range(7):
            analyzer.record(_rec(incident_id=f"inc-{i}"))
        report = analyzer.analyze()
        assert report.total_disagreements == 7

    # ---- by_kind counts ----------------------------------------------------

    def test_by_kind_override_count(self) -> None:
        analyzer = DisagreementAnalyzer()
        analyzer.record(_rec(kind=DisagreementKind.OVERRIDE))
        analyzer.record(_rec(kind=DisagreementKind.OVERRIDE, incident_id="inc-2"))
        analyzer.record(_rec(kind=DisagreementKind.REJECTION, incident_id="inc-3"))
        report = analyzer.analyze()
        assert report.by_kind[DisagreementKind.OVERRIDE.value] == 2
        assert report.by_kind[DisagreementKind.REJECTION.value] == 1

    def test_by_kind_all_kinds_tracked(self) -> None:
        analyzer = DisagreementAnalyzer()
        for i, kind in enumerate(DisagreementKind):
            analyzer.record(_rec(kind=kind, incident_id=f"inc-{i}"))
        report = analyzer.analyze()
        for kind in DisagreementKind:
            assert report.by_kind[kind.value] == 1

    # ---- Unjustified override count ----------------------------------------

    def test_unjustified_override_count_correct(self) -> None:
        analyzer = DisagreementAnalyzer()
        analyzer.record(_rec(kind=DisagreementKind.OVERRIDE, has_justification=True))
        analyzer.record(
            _rec(kind=DisagreementKind.OVERRIDE, has_justification=False, incident_id="inc-2")
        )
        analyzer.record(
            _rec(kind=DisagreementKind.OVERRIDE, has_justification=False, incident_id="inc-3")
        )
        report = analyzer.analyze()
        assert report.unjustified_override_count == 2

    def test_justified_overrides_not_counted(self) -> None:
        analyzer = DisagreementAnalyzer()
        analyzer.record(_rec(kind=DisagreementKind.OVERRIDE, has_justification=True))
        analyzer.record(
            _rec(kind=DisagreementKind.OVERRIDE, has_justification=True, incident_id="inc-2")
        )
        report = analyzer.analyze()
        assert report.unjustified_override_count == 0

    def test_non_override_unjustified_not_counted(self) -> None:
        analyzer = DisagreementAnalyzer()
        # Rejection with no justification should NOT count as unjustified override
        analyzer.record(_rec(kind=DisagreementKind.REJECTION, has_justification=False))
        report = analyzer.analyze()
        assert report.unjustified_override_count == 0

    # ---- Systematic rejection detection ------------------------------------

    def test_systematic_rejection_detected_above_30_pct(self) -> None:
        analyzer = DisagreementAnalyzer()
        # 4 rejections out of 10 total = 40% > 30%
        for i in range(4):
            analyzer.record(_rec(kind=DisagreementKind.REJECTION, incident_id=f"rej-{i}"))
        for i in range(6):
            analyzer.record(_rec(kind=DisagreementKind.OVERRIDE, incident_id=f"ovr-{i}"))
        report = analyzer.analyze()
        assert report.systematic_rejection_detected is True

    def test_systematic_rejection_not_detected_at_30_pct(self) -> None:
        analyzer = DisagreementAnalyzer()
        # Exactly 30%: 3 rejections out of 10 = 30% — NOT > 30%
        for i in range(3):
            analyzer.record(_rec(kind=DisagreementKind.REJECTION, incident_id=f"rej-{i}"))
        for i in range(7):
            analyzer.record(_rec(kind=DisagreementKind.OVERRIDE, incident_id=f"ovr-{i}"))
        report = analyzer.analyze()
        assert report.systematic_rejection_detected is False

    def test_systematic_rejection_not_detected_below_30_pct(self) -> None:
        analyzer = DisagreementAnalyzer()
        for i in range(2):
            analyzer.record(_rec(kind=DisagreementKind.REJECTION, incident_id=f"rej-{i}"))
        for i in range(8):
            analyzer.record(_rec(kind=DisagreementKind.OVERRIDE, incident_id=f"ovr-{i}"))
        report = analyzer.analyze()
        assert report.systematic_rejection_detected is False

    # ---- Silent bypass detection -------------------------------------------

    def test_silent_bypass_detected_when_any_bypass_exists(self) -> None:
        analyzer = DisagreementAnalyzer()
        analyzer.record(_rec(kind=DisagreementKind.SILENT_BYPASS))
        report = analyzer.analyze()
        assert report.silent_bypass_detected is True

    def test_silent_bypass_not_detected_without_bypass(self) -> None:
        analyzer = DisagreementAnalyzer()
        analyzer.record(_rec(kind=DisagreementKind.OVERRIDE))
        analyzer.record(_rec(kind=DisagreementKind.REJECTION, incident_id="inc-2"))
        report = analyzer.analyze()
        assert report.silent_bypass_detected is False

    # ---- CHRONIC_OVERRIDE pattern -------------------------------------------

    def test_chronic_override_detected_above_3_overrides_per_operator(self) -> None:
        analyzer = DisagreementAnalyzer()
        # op-chronic has 4 overrides
        for i in range(4):
            analyzer.record(
                _rec(
                    operator_id="op-chronic",
                    kind=DisagreementKind.OVERRIDE,
                    incident_id=f"inc-{i}",
                )
            )
        report = analyzer.analyze()
        pattern_names = [p.pattern_name for p in report.patterns]
        assert "CHRONIC_OVERRIDE" in pattern_names

    def test_chronic_override_risk_is_high(self) -> None:
        analyzer = DisagreementAnalyzer()
        for i in range(4):
            analyzer.record(
                _rec(
                    operator_id="op-c2",
                    kind=DisagreementKind.OVERRIDE,
                    incident_id=f"inc-{i}",
                )
            )
        report = analyzer.analyze()
        chronic = next(p for p in report.patterns if p.pattern_name == "CHRONIC_OVERRIDE")
        assert chronic.risk_level == "HIGH"

    def test_chronic_override_affected_operator_in_list(self) -> None:
        analyzer = DisagreementAnalyzer()
        for i in range(4):
            analyzer.record(
                _rec(
                    operator_id="op-c3",
                    kind=DisagreementKind.OVERRIDE,
                    incident_id=f"inc-{i}",
                )
            )
        report = analyzer.analyze()
        chronic = next(p for p in report.patterns if p.pattern_name == "CHRONIC_OVERRIDE")
        assert "op-c3" in chronic.affected_operator_ids

    def test_chronic_override_not_detected_with_3_or_fewer_overrides(self) -> None:
        analyzer = DisagreementAnalyzer()
        for i in range(3):
            analyzer.record(
                _rec(
                    operator_id="op-safe",
                    kind=DisagreementKind.OVERRIDE,
                    incident_id=f"inc-{i}",
                )
            )
        report = analyzer.analyze()
        pattern_names = [p.pattern_name for p in report.patterns]
        assert "CHRONIC_OVERRIDE" not in pattern_names

    # ---- REJECTION_CLUSTER pattern -----------------------------------------

    def test_rejection_cluster_detected_above_30_pct(self) -> None:
        analyzer = DisagreementAnalyzer()
        for i in range(4):
            analyzer.record(_rec(kind=DisagreementKind.REJECTION, incident_id=f"rej-{i}"))
        for i in range(6):
            analyzer.record(_rec(kind=DisagreementKind.OVERRIDE, incident_id=f"ovr-{i}"))
        report = analyzer.analyze()
        pattern_names = [p.pattern_name for p in report.patterns]
        assert "REJECTION_CLUSTER" in pattern_names

    def test_rejection_cluster_risk_is_medium(self) -> None:
        analyzer = DisagreementAnalyzer()
        for i in range(4):
            analyzer.record(_rec(kind=DisagreementKind.REJECTION, incident_id=f"rej-{i}"))
        for i in range(6):
            analyzer.record(_rec(kind=DisagreementKind.OVERRIDE, incident_id=f"ovr-{i}"))
        report = analyzer.analyze()
        cluster = next(p for p in report.patterns if p.pattern_name == "REJECTION_CLUSTER")
        assert cluster.risk_level == "MEDIUM"

    def test_rejection_cluster_not_detected_at_or_below_30_pct(self) -> None:
        analyzer = DisagreementAnalyzer()
        for i in range(3):
            analyzer.record(_rec(kind=DisagreementKind.REJECTION, incident_id=f"rej-{i}"))
        for i in range(7):
            analyzer.record(_rec(kind=DisagreementKind.OVERRIDE, incident_id=f"ovr-{i}"))
        report = analyzer.analyze()
        pattern_names = [p.pattern_name for p in report.patterns]
        assert "REJECTION_CLUSTER" not in pattern_names

    # ---- SILENT_BYPASS_RISK pattern ----------------------------------------

    def test_silent_bypass_risk_pattern_detected(self) -> None:
        analyzer = DisagreementAnalyzer()
        analyzer.record(_rec(kind=DisagreementKind.SILENT_BYPASS, operator_id="op-sneak"))
        report = analyzer.analyze()
        pattern_names = [p.pattern_name for p in report.patterns]
        assert "SILENT_BYPASS_RISK" in pattern_names

    def test_silent_bypass_risk_is_high(self) -> None:
        analyzer = DisagreementAnalyzer()
        analyzer.record(_rec(kind=DisagreementKind.SILENT_BYPASS, operator_id="op-sneak2"))
        report = analyzer.analyze()
        bypass = next(p for p in report.patterns if p.pattern_name == "SILENT_BYPASS_RISK")
        assert bypass.risk_level == "HIGH"

    def test_silent_bypass_risk_includes_operator_id(self) -> None:
        analyzer = DisagreementAnalyzer()
        analyzer.record(_rec(kind=DisagreementKind.SILENT_BYPASS, operator_id="op-sneak3"))
        report = analyzer.analyze()
        bypass = next(p for p in report.patterns if p.pattern_name == "SILENT_BYPASS_RISK")
        assert "op-sneak3" in bypass.affected_operator_ids

    def test_silent_bypass_risk_not_detected_without_bypass(self) -> None:
        analyzer = DisagreementAnalyzer()
        analyzer.record(_rec(kind=DisagreementKind.OVERRIDE))
        report = analyzer.analyze()
        pattern_names = [p.pattern_name for p in report.patterns]
        assert "SILENT_BYPASS_RISK" not in pattern_names

    # ---- DisagreementPattern dataclass -------------------------------------

    def test_pattern_is_dataclass(self) -> None:
        analyzer = DisagreementAnalyzer()
        analyzer.record(_rec(kind=DisagreementKind.SILENT_BYPASS))
        report = analyzer.analyze()
        assert all(isinstance(p, DisagreementPattern) for p in report.patterns)

    def test_patterns_list_empty_when_no_patterns(self) -> None:
        analyzer = DisagreementAnalyzer()
        analyzer.record(_rec(kind=DisagreementKind.DELAYED_ACTION))
        report = analyzer.analyze()
        # DELAYED_ACTION alone should not trigger any pattern
        pattern_names = [p.pattern_name for p in report.patterns]
        assert "CHRONIC_OVERRIDE" not in pattern_names
        assert "REJECTION_CLUSTER" not in pattern_names
        assert "SILENT_BYPASS_RISK" not in pattern_names

    # ---- Multiple patterns simultaneously ----------------------------------

    def test_multiple_patterns_can_coexist(self) -> None:
        analyzer = DisagreementAnalyzer()
        # CHRONIC_OVERRIDE: op-multi has 4 overrides
        for i in range(4):
            analyzer.record(
                _rec(
                    operator_id="op-multi",
                    kind=DisagreementKind.OVERRIDE,
                    incident_id=f"ovr-{i}",
                )
            )
        # SILENT_BYPASS_RISK: one bypass
        analyzer.record(_rec(kind=DisagreementKind.SILENT_BYPASS, incident_id="bypass-1"))
        # Add rejections to push above 30% threshold
        # Total: 5 overrides + 1 bypass = 6. Need rejections > 30% of total.
        # Add 3 rejections → total 9, rejections 3/9 = 33%
        for i in range(3):
            analyzer.record(_rec(kind=DisagreementKind.REJECTION, incident_id=f"rej-{i}"))
        report = analyzer.analyze()
        pattern_names = [p.pattern_name for p in report.patterns]
        assert "CHRONIC_OVERRIDE" in pattern_names
        assert "SILENT_BYPASS_RISK" in pattern_names
        assert "REJECTION_CLUSTER" in pattern_names
