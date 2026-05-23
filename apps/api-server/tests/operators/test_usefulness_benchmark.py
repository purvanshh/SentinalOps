"""
Tests for Phase 49 Commit 6 — operational usefulness benchmarking modules:
  - WorkflowBenchmark          (workflow_benchmark.py)
  - OperationalUsefulnessEvaluator (usefulness_evaluator.py)
  - LongitudinalOperatorEvaluator  (longitudinal_operator_eval.py)
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

import pytest
from operators.workflow.longitudinal_operator_eval import (
    LongitudinalOperatorEvaluator,
    LongitudinalTrend,
    SessionSummary,
)
from operators.workflow.usefulness_evaluator import (
    OperationalUsefulnessEvaluator,
    OperationalUsefulnessReport,
)
from operators.workflow.workflow_benchmark import (
    WorkflowBenchmark,
    WorkflowBenchmarkResult,
)

# ===========================================================================
# Helpers
# ===========================================================================


def _make_benchmark() -> WorkflowBenchmark:
    return WorkflowBenchmark()


def _make_evaluator() -> OperationalUsefulnessEvaluator:
    return OperationalUsefulnessEvaluator()


def _make_long_evaluator() -> LongitudinalOperatorEvaluator:
    return LongitudinalOperatorEvaluator()


def _default_run(
    benchmark: WorkflowBenchmark,
    incident_id: str = "inc-001",
    auto_resolved: bool = True,
    unnecessary_escalations: int = 0,
    total_escalations: int = 1,
    ambiguity_resolved: bool = True,
    confidence_at_resolution: float = 0.9,
    remediation_usefulness: float = 0.8,
    rollbacks: int = 0,
    trust_score: float = 0.85,
    decision_latency_seconds: float = 30.0,
    max_latency_seconds: float = 300.0,
    overrides: int = 0,
    total_recommendations: int = 5,
    explanation_quality: float = 0.9,
) -> WorkflowBenchmarkResult:
    return benchmark.run(
        incident_id=incident_id,
        auto_resolved=auto_resolved,
        unnecessary_escalations=unnecessary_escalations,
        total_escalations=total_escalations,
        ambiguity_resolved=ambiguity_resolved,
        confidence_at_resolution=confidence_at_resolution,
        remediation_usefulness=remediation_usefulness,
        rollbacks=rollbacks,
        trust_score=trust_score,
        decision_latency_seconds=decision_latency_seconds,
        max_latency_seconds=max_latency_seconds,
        overrides=overrides,
        total_recommendations=total_recommendations,
        explanation_quality=explanation_quality,
    )


def _default_evaluate(
    evaluator: OperationalUsefulnessEvaluator,
    session_id: str = "sess-001",
    workflow_quality: float = 0.8,
    operator_alignment: float = 0.8,
    escalation_burden: float = 0.2,
    recommendation_quality: float = 0.8,
    cognitive_load_score: float = 0.3,
    trust_stability: float = 0.8,
    remediation_usefulness: float = 0.75,
    explainability_quality: float = 0.75,
) -> OperationalUsefulnessReport:
    return evaluator.evaluate(
        session_id=session_id,
        workflow_quality=workflow_quality,
        operator_alignment=operator_alignment,
        escalation_burden=escalation_burden,
        recommendation_quality=recommendation_quality,
        cognitive_load_score=cognitive_load_score,
        trust_stability=trust_stability,
        remediation_usefulness=remediation_usefulness,
        explainability_quality=explainability_quality,
    )


def _make_session(
    session_id: str,
    operator_id: str,
    usefulness_score: float = 0.7,
    trust_at_end: float = 0.7,
    incidents_handled: int = 3,
    overrides: int = 1,
    escalations: int = 2,
) -> SessionSummary:
    return SessionSummary(
        session_id=session_id,
        operator_id=operator_id,
        usefulness_score=usefulness_score,
        trust_at_end=trust_at_end,
        incidents_handled=incidents_handled,
        overrides=overrides,
        escalations=escalations,
    )


# ===========================================================================
# WorkflowBenchmark
# ===========================================================================


class TestWorkflowBenchmark:
    # ---- Return type -------------------------------------------------------

    def test_returns_benchmark_result_dataclass(self) -> None:
        result = _default_run(_make_benchmark())
        assert isinstance(result, WorkflowBenchmarkResult)

    def test_incident_id_preserved(self) -> None:
        result = _default_run(_make_benchmark(), incident_id="myinc-42")
        assert result.incident_id == "myinc-42"

    # ---- All scores bounded [0, 1] ----------------------------------------

    def test_all_component_scores_bounded_0_to_1(self) -> None:
        result = _default_run(_make_benchmark())
        for attr in [
            "workload_reduction_score",
            "escalation_reduction_score",
            "ambiguity_handling_quality",
            "remediation_usefulness_score",
            "rollback_avoidance_score",
            "trust_preservation_score",
            "decision_latency_score",
            "override_necessity_score",
            "explanation_usefulness_score",
            "overall_benchmark_score",
        ]:
            value = getattr(result, attr)
            assert 0.0 <= value <= 1.0, f"{attr}={value} out of [0, 1]"

    # ---- workload_reduction_score -----------------------------------------

    def test_auto_resolved_workload_reduction_is_1(self) -> None:
        result = _default_run(_make_benchmark(), auto_resolved=True)
        assert result.workload_reduction_score == pytest.approx(1.0)

    def test_not_auto_resolved_no_overrides_workload_is_0_5(self) -> None:
        result = _default_run(_make_benchmark(), auto_resolved=False, overrides=0)
        assert result.workload_reduction_score == pytest.approx(0.5)

    def test_not_auto_resolved_2_overrides_workload_is_0_4(self) -> None:
        result = _default_run(_make_benchmark(), auto_resolved=False, overrides=2)
        assert result.workload_reduction_score == pytest.approx(0.4)

    def test_not_auto_resolved_many_overrides_floors_at_0(self) -> None:
        # 0.5 - 0.05 * 20 = -0.5 → clamped to 0.0
        result = _default_run(_make_benchmark(), auto_resolved=False, overrides=20)
        assert result.workload_reduction_score == pytest.approx(0.0)

    def test_not_auto_resolved_10_overrides_exactly_zero(self) -> None:
        # 0.5 - 0.05 * 10 = 0.0
        result = _default_run(_make_benchmark(), auto_resolved=False, overrides=10)
        assert result.workload_reduction_score == pytest.approx(0.0)

    # ---- escalation_reduction_score ---------------------------------------

    def test_no_unnecessary_escalations_score_is_1(self) -> None:
        result = _default_run(_make_benchmark(), unnecessary_escalations=0, total_escalations=5)
        assert result.escalation_reduction_score == pytest.approx(1.0)

    def test_all_escalations_unnecessary_score_is_0(self) -> None:
        result = _default_run(_make_benchmark(), unnecessary_escalations=4, total_escalations=4)
        assert result.escalation_reduction_score == pytest.approx(0.0)

    def test_half_unnecessary_score_is_0_5(self) -> None:
        result = _default_run(_make_benchmark(), unnecessary_escalations=2, total_escalations=4)
        assert result.escalation_reduction_score == pytest.approx(0.5)

    def test_zero_total_escalations_uses_max_1_guard(self) -> None:
        # 0 unnecessary / max(0, 1) = 0 → score = 1.0
        result = _default_run(_make_benchmark(), unnecessary_escalations=0, total_escalations=0)
        assert result.escalation_reduction_score == pytest.approx(1.0)

    def test_more_unnecessary_than_total_clamped_to_0(self) -> None:
        result = _default_run(_make_benchmark(), unnecessary_escalations=10, total_escalations=3)
        assert result.escalation_reduction_score == pytest.approx(0.0)

    # ---- ambiguity_handling_quality ---------------------------------------

    def test_ambiguity_resolved_returns_confidence(self) -> None:
        result = _default_run(
            _make_benchmark(),
            ambiguity_resolved=True,
            confidence_at_resolution=0.75,
        )
        assert result.ambiguity_handling_quality == pytest.approx(0.75)

    def test_ambiguity_not_resolved_halves_confidence(self) -> None:
        result = _default_run(
            _make_benchmark(),
            ambiguity_resolved=False,
            confidence_at_resolution=0.80,
        )
        assert result.ambiguity_handling_quality == pytest.approx(0.40)

    def test_ambiguity_not_resolved_zero_confidence(self) -> None:
        result = _default_run(
            _make_benchmark(),
            ambiguity_resolved=False,
            confidence_at_resolution=0.0,
        )
        assert result.ambiguity_handling_quality == pytest.approx(0.0)

    # ---- rollback_avoidance_score -----------------------------------------

    def test_no_rollbacks_score_is_1(self) -> None:
        result = _default_run(_make_benchmark(), rollbacks=0)
        assert result.rollback_avoidance_score == pytest.approx(1.0)

    def test_one_rollback_score_is_0_75(self) -> None:
        result = _default_run(_make_benchmark(), rollbacks=1)
        assert result.rollback_avoidance_score == pytest.approx(0.75)

    def test_two_rollbacks_score_is_0_5(self) -> None:
        result = _default_run(_make_benchmark(), rollbacks=2)
        assert result.rollback_avoidance_score == pytest.approx(0.5)

    def test_four_rollbacks_score_is_0(self) -> None:
        result = _default_run(_make_benchmark(), rollbacks=4)
        assert result.rollback_avoidance_score == pytest.approx(0.0)

    def test_five_rollbacks_floored_at_0(self) -> None:
        result = _default_run(_make_benchmark(), rollbacks=5)
        assert result.rollback_avoidance_score == pytest.approx(0.0)

    # ---- trust_preservation_score -----------------------------------------

    def test_trust_score_passed_through_directly(self) -> None:
        result = _default_run(_make_benchmark(), trust_score=0.65)
        assert result.trust_preservation_score == pytest.approx(0.65)

    # ---- decision_latency_score -------------------------------------------

    def test_zero_latency_gives_score_1(self) -> None:
        result = _default_run(
            _make_benchmark(),
            decision_latency_seconds=0.0,
            max_latency_seconds=300.0,
        )
        assert result.decision_latency_score == pytest.approx(1.0)

    def test_latency_equals_max_gives_score_0(self) -> None:
        result = _default_run(
            _make_benchmark(),
            decision_latency_seconds=300.0,
            max_latency_seconds=300.0,
        )
        assert result.decision_latency_score == pytest.approx(0.0)

    def test_latency_half_of_max_gives_score_0_5(self) -> None:
        result = _default_run(
            _make_benchmark(),
            decision_latency_seconds=150.0,
            max_latency_seconds=300.0,
        )
        assert result.decision_latency_score == pytest.approx(0.5)

    def test_latency_exceeds_max_clamped_to_0(self) -> None:
        result = _default_run(
            _make_benchmark(),
            decision_latency_seconds=400.0,
            max_latency_seconds=300.0,
        )
        assert result.decision_latency_score == pytest.approx(0.0)

    # ---- override_necessity_score -----------------------------------------

    def test_no_overrides_score_is_1(self) -> None:
        result = _default_run(_make_benchmark(), overrides=0, total_recommendations=5)
        assert result.override_necessity_score == pytest.approx(1.0)

    def test_overrides_equals_total_recs_score_is_0(self) -> None:
        result = _default_run(_make_benchmark(), overrides=5, total_recommendations=5)
        assert result.override_necessity_score == pytest.approx(0.0)

    def test_one_override_of_four_recs_score_is_0_75(self) -> None:
        result = _default_run(_make_benchmark(), overrides=1, total_recommendations=4)
        assert result.override_necessity_score == pytest.approx(0.75)

    def test_overrides_exceed_recs_floored_at_0(self) -> None:
        result = _default_run(_make_benchmark(), overrides=10, total_recommendations=4)
        assert result.override_necessity_score == pytest.approx(0.0)

    def test_zero_total_recs_uses_max_1_guard(self) -> None:
        # overrides=0, total_recs=0 → 1 - 0/1 = 1.0
        result = _default_run(_make_benchmark(), overrides=0, total_recommendations=0)
        assert result.override_necessity_score == pytest.approx(1.0)

    # ---- explanation_usefulness_score -------------------------------------

    def test_explanation_quality_passed_through_directly(self) -> None:
        result = _default_run(_make_benchmark(), explanation_quality=0.72)
        assert result.explanation_usefulness_score == pytest.approx(0.72)

    # ---- overall_benchmark_score (equal-weighted mean of 9 scores) --------

    def test_perfect_inputs_overall_is_1(self) -> None:
        result = _make_benchmark().run(
            incident_id="perfect",
            auto_resolved=True,
            unnecessary_escalations=0,
            total_escalations=5,
            ambiguity_resolved=True,
            confidence_at_resolution=1.0,
            remediation_usefulness=1.0,
            rollbacks=0,
            trust_score=1.0,
            decision_latency_seconds=0.0,
            max_latency_seconds=300.0,
            overrides=0,
            total_recommendations=5,
            explanation_quality=1.0,
        )
        assert result.overall_benchmark_score == pytest.approx(1.0)

    def test_overall_is_mean_of_nine_components(self) -> None:
        result = _default_run(_make_benchmark())
        expected = (
            result.workload_reduction_score
            + result.escalation_reduction_score
            + result.ambiguity_handling_quality
            + result.remediation_usefulness_score
            + result.rollback_avoidance_score
            + result.trust_preservation_score
            + result.decision_latency_score
            + result.override_necessity_score
            + result.explanation_usefulness_score
        ) / 9.0
        assert result.overall_benchmark_score == pytest.approx(expected)

    def test_all_zero_inputs_overall_is_0_or_near(self) -> None:
        # auto_resolved=False, overrides=10 → workload = max(0, 0.5-0.5) = 0.0
        # unnecessary=1/total=1 → escalation_reduction = 0.0
        # ambiguity_resolved=False, confidence=0 → ambiguity = 0.0
        # remediation_usefulness=0 → 0.0
        # rollbacks=4 → rollback_avoidance = max(0, 1-1.0) = 0.0
        # trust=0.0 → 0.0
        # latency=max / latency=max → 0.0
        # overrides=10, total_recs=5 → override_necessity = max(0, 1-2) = 0.0
        # explanation=0 → 0.0
        result = _make_benchmark().run(
            incident_id="zero",
            auto_resolved=False,
            unnecessary_escalations=1,
            total_escalations=1,
            ambiguity_resolved=False,
            confidence_at_resolution=0.0,
            remediation_usefulness=0.0,
            rollbacks=4,
            trust_score=0.0,
            decision_latency_seconds=300.0,
            max_latency_seconds=300.0,
            overrides=10,
            total_recommendations=5,
            explanation_quality=0.0,
        )
        assert result.overall_benchmark_score == pytest.approx(0.0)

    # ---- Edge case: remediation_usefulness passed directly ----------------

    def test_remediation_usefulness_passed_directly(self) -> None:
        result = _default_run(_make_benchmark(), remediation_usefulness=0.55)
        assert result.remediation_usefulness_score == pytest.approx(0.55)


# ===========================================================================
# OperationalUsefulnessEvaluator
# ===========================================================================


class TestOperationalUsefulnessEvaluator:
    # ---- Return type -------------------------------------------------------

    def test_returns_report_dataclass(self) -> None:
        result = _default_evaluate(_make_evaluator())
        assert isinstance(result, OperationalUsefulnessReport)

    def test_session_id_preserved(self) -> None:
        result = _default_evaluate(_make_evaluator(), session_id="my-session")
        assert result.session_id == "my-session"

    # ---- overall_usefulness formula ---------------------------------------

    def test_all_perfect_inputs_overall_near_1(self) -> None:
        result = _make_evaluator().evaluate(
            session_id="s",
            workflow_quality=1.0,
            operator_alignment=1.0,
            escalation_burden=0.0,
            recommendation_quality=1.0,
            cognitive_load_score=0.0,
            trust_stability=1.0,
            remediation_usefulness=1.0,
            explainability_quality=1.0,
        )
        assert result.overall_usefulness == pytest.approx(1.0)

    def test_all_zero_inputs_overall_is_0(self) -> None:
        result = _make_evaluator().evaluate(
            session_id="s",
            workflow_quality=0.0,
            operator_alignment=0.0,
            escalation_burden=1.0,  # (1 - 1.0) * 0.10 = 0
            recommendation_quality=0.0,
            cognitive_load_score=1.0,  # (1 - 1.0) * 0.10 = 0
            trust_stability=0.0,
            remediation_usefulness=0.0,
            explainability_quality=0.0,
        )
        assert result.overall_usefulness == pytest.approx(0.0)

    def test_formula_weighted_correctly(self) -> None:
        wq, oa, eb, rq, cl, ts, ru, eq = 0.8, 0.7, 0.3, 0.9, 0.2, 0.75, 0.6, 0.65
        expected = (
            0.15 * wq
            + 0.15 * oa
            + 0.10 * (1.0 - eb)
            + 0.15 * rq
            + 0.10 * (1.0 - cl)
            + 0.15 * ts
            + 0.10 * ru
            + 0.10 * eq
        )
        result = _make_evaluator().evaluate(
            session_id="s",
            workflow_quality=wq,
            operator_alignment=oa,
            escalation_burden=eb,
            recommendation_quality=rq,
            cognitive_load_score=cl,
            trust_stability=ts,
            remediation_usefulness=ru,
            explainability_quality=eq,
        )
        assert result.overall_usefulness == pytest.approx(expected)

    def test_workflow_quality_weight_is_0_15(self) -> None:
        # Only workflow_quality contributes; all others zero.
        result = _make_evaluator().evaluate(
            session_id="s",
            workflow_quality=1.0,
            operator_alignment=0.0,
            escalation_burden=1.0,
            recommendation_quality=0.0,
            cognitive_load_score=1.0,
            trust_stability=0.0,
            remediation_usefulness=0.0,
            explainability_quality=0.0,
        )
        assert result.overall_usefulness == pytest.approx(0.15)

    def test_escalation_burden_inverted_in_formula(self) -> None:
        # escalation_burden=0.0 → contribution = 0.10 * 1.0 = 0.10
        # escalation_burden=1.0 → contribution = 0.10 * 0.0 = 0.0
        r_low = _make_evaluator().evaluate(
            "s",
            0,
            0,
            escalation_burden=0.0,
            recommendation_quality=0,
            cognitive_load_score=0,
            trust_stability=0,
            remediation_usefulness=0,
            explainability_quality=0,
        )
        r_high = _make_evaluator().evaluate(
            "s",
            0,
            0,
            escalation_burden=1.0,
            recommendation_quality=0,
            cognitive_load_score=0,
            trust_stability=0,
            remediation_usefulness=0,
            explainability_quality=0,
        )
        assert r_low.overall_usefulness > r_high.overall_usefulness

    def test_cognitive_load_inverted_in_formula(self) -> None:
        r_low = _make_evaluator().evaluate(
            "s",
            0,
            0,
            escalation_burden=0,
            recommendation_quality=0,
            cognitive_load_score=0.0,
            trust_stability=0,
            remediation_usefulness=0,
            explainability_quality=0,
        )
        r_high = _make_evaluator().evaluate(
            "s",
            0,
            0,
            escalation_burden=0,
            recommendation_quality=0,
            cognitive_load_score=1.0,
            trust_stability=0,
            remediation_usefulness=0,
            explainability_quality=0,
        )
        assert r_low.overall_usefulness > r_high.overall_usefulness

    # ---- is_operationally_useful threshold (0.55) -------------------------

    def test_overall_above_0_55_is_useful(self) -> None:
        # Craft inputs so overall = ~0.70 (clearly above threshold)
        result = _default_evaluate(_make_evaluator())
        assert result.overall_usefulness >= 0.55
        assert result.is_operationally_useful is True

    def test_overall_below_0_55_is_not_useful(self) -> None:
        result = _make_evaluator().evaluate(
            session_id="s",
            workflow_quality=0.2,
            operator_alignment=0.2,
            escalation_burden=0.9,
            recommendation_quality=0.2,
            cognitive_load_score=0.9,
            trust_stability=0.2,
            remediation_usefulness=0.2,
            explainability_quality=0.2,
        )
        assert result.overall_usefulness < 0.55
        assert result.is_operationally_useful is False

    def test_overall_exactly_0_55_is_useful(self) -> None:
        # Construct an exact 0.55 scenario via the formula:
        # 0.15*wq + 0.15*oa + 0.10*(1-eb) + 0.15*rq + 0.10*(1-cl)
        # + 0.15*ts + 0.10*ru + 0.10*eq = 0.55
        # Easy: all contribute equally → x*(0.15+0.15+0.10+0.15+0.10+0.15+0.10+0.10)=0.55
        # Weights sum to 1.0 → x=0.55; but burden/load are inverted so set them to 1-0.55=0.45
        result = _make_evaluator().evaluate(
            session_id="s",
            workflow_quality=0.55,
            operator_alignment=0.55,
            escalation_burden=0.45,  # (1 - 0.45) = 0.55
            recommendation_quality=0.55,
            cognitive_load_score=0.45,  # (1 - 0.45) = 0.55
            trust_stability=0.55,
            remediation_usefulness=0.55,
            explainability_quality=0.55,
        )
        assert result.overall_usefulness == pytest.approx(0.55, abs=1e-9)
        assert result.is_operationally_useful is True

    # ---- improvement_areas detection -------------------------------------

    def test_no_improvement_areas_when_all_good(self) -> None:
        result = _default_evaluate(_make_evaluator())
        assert result.improvement_areas == []

    def test_low_workflow_quality_flagged(self) -> None:
        result = _make_evaluator().evaluate(
            "s",
            workflow_quality=0.3,
            operator_alignment=0.8,
            escalation_burden=0.2,
            recommendation_quality=0.8,
            cognitive_load_score=0.2,
            trust_stability=0.8,
            remediation_usefulness=0.7,
            explainability_quality=0.7,
        )
        assert "workflow_quality" in result.improvement_areas

    def test_high_escalation_burden_flagged(self) -> None:
        # (1 - 0.8) = 0.2 < 0.5 → flagged
        result = _make_evaluator().evaluate(
            "s",
            workflow_quality=0.8,
            operator_alignment=0.8,
            escalation_burden=0.8,
            recommendation_quality=0.8,
            cognitive_load_score=0.2,
            trust_stability=0.8,
            remediation_usefulness=0.7,
            explainability_quality=0.7,
        )
        assert "escalation_burden" in result.improvement_areas

    def test_high_cognitive_load_flagged(self) -> None:
        # (1 - 0.8) = 0.2 < 0.5 → flagged
        result = _make_evaluator().evaluate(
            "s",
            workflow_quality=0.8,
            operator_alignment=0.8,
            escalation_burden=0.2,
            recommendation_quality=0.8,
            cognitive_load_score=0.8,
            trust_stability=0.8,
            remediation_usefulness=0.7,
            explainability_quality=0.7,
        )
        assert "cognitive_load_score" in result.improvement_areas

    def test_multiple_low_fields_all_flagged(self) -> None:
        result = _make_evaluator().evaluate(
            "s",
            workflow_quality=0.3,
            operator_alignment=0.4,
            escalation_burden=0.1,
            recommendation_quality=0.3,
            cognitive_load_score=0.2,
            trust_stability=0.4,
            remediation_usefulness=0.3,
            explainability_quality=0.4,
        )
        for area in [
            "workflow_quality",
            "operator_alignment",
            "recommendation_quality",
            "trust_stability",
            "remediation_usefulness",
            "explainability_quality",
        ]:
            assert area in result.improvement_areas

    def test_boundary_exactly_0_50_not_flagged(self) -> None:
        # Fields at exactly 0.50 should NOT be in improvement_areas (< 0.50 threshold)
        result = _make_evaluator().evaluate(
            "s",
            workflow_quality=0.50,
            operator_alignment=0.50,
            escalation_burden=0.50,  # (1 - 0.50) = 0.50
            recommendation_quality=0.50,
            cognitive_load_score=0.50,  # (1 - 0.50) = 0.50
            trust_stability=0.50,
            remediation_usefulness=0.50,
            explainability_quality=0.50,
        )
        assert result.improvement_areas == []

    def test_boundary_just_below_0_50_flagged(self) -> None:
        result = _make_evaluator().evaluate(
            "s",
            workflow_quality=0.49,
            operator_alignment=0.8,
            escalation_burden=0.2,
            recommendation_quality=0.8,
            cognitive_load_score=0.2,
            trust_stability=0.8,
            remediation_usefulness=0.7,
            explainability_quality=0.7,
        )
        assert "workflow_quality" in result.improvement_areas

    def test_input_fields_stored_in_report(self) -> None:
        result = _make_evaluator().evaluate(
            session_id="s99",
            workflow_quality=0.7,
            operator_alignment=0.6,
            escalation_burden=0.3,
            recommendation_quality=0.75,
            cognitive_load_score=0.4,
            trust_stability=0.65,
            remediation_usefulness=0.55,
            explainability_quality=0.60,
        )
        assert result.workflow_quality == pytest.approx(0.7)
        assert result.operator_alignment == pytest.approx(0.6)
        assert result.escalation_burden == pytest.approx(0.3)
        assert result.recommendation_quality == pytest.approx(0.75)
        assert result.cognitive_load_score == pytest.approx(0.4)
        assert result.trust_stability == pytest.approx(0.65)
        assert result.remediation_usefulness == pytest.approx(0.55)
        assert result.explainability_quality == pytest.approx(0.60)


# ===========================================================================
# LongitudinalOperatorEvaluator
# ===========================================================================


class TestLongitudinalOperatorEvaluator:
    # ---- Basic round-trip --------------------------------------------------

    def test_evaluate_operator_with_no_sessions_returns_default_trend(self) -> None:
        evaluator = _make_long_evaluator()
        trend = evaluator.evaluate_operator("op-unknown")
        assert isinstance(trend, LongitudinalTrend)
        assert trend.session_count == 0
        assert trend.mean_usefulness == pytest.approx(0.0)
        assert trend.usefulness_trend == "STABLE"

    def test_single_session_returns_stable_trend(self) -> None:
        evaluator = _make_long_evaluator()
        evaluator.add_session(_make_session("s1", "op1", usefulness_score=0.8))
        trend = evaluator.evaluate_operator("op1")
        assert trend.session_count == 1
        assert trend.mean_usefulness == pytest.approx(0.8)
        assert trend.usefulness_trend == "STABLE"

    def test_mean_usefulness_is_average_of_sessions(self) -> None:
        evaluator = _make_long_evaluator()
        evaluator.add_session(_make_session("s1", "op1", usefulness_score=0.6))
        evaluator.add_session(_make_session("s2", "op1", usefulness_score=0.8))
        trend = evaluator.evaluate_operator("op1")
        assert trend.mean_usefulness == pytest.approx(0.7)

    def test_total_incidents_summed(self) -> None:
        evaluator = _make_long_evaluator()
        evaluator.add_session(_make_session("s1", "op1", incidents_handled=3))
        evaluator.add_session(_make_session("s2", "op1", incidents_handled=5))
        trend = evaluator.evaluate_operator("op1")
        assert trend.total_incidents == 8

    def test_total_overrides_summed(self) -> None:
        evaluator = _make_long_evaluator()
        evaluator.add_session(_make_session("s1", "op1", overrides=2))
        evaluator.add_session(_make_session("s2", "op1", overrides=3))
        trend = evaluator.evaluate_operator("op1")
        assert trend.total_overrides == 5

    def test_total_escalations_summed(self) -> None:
        evaluator = _make_long_evaluator()
        evaluator.add_session(_make_session("s1", "op1", escalations=1))
        evaluator.add_session(_make_session("s2", "op1", escalations=4))
        trend = evaluator.evaluate_operator("op1")
        assert trend.total_escalations == 5

    # ---- Trend detection (usefulness) -------------------------------------

    def test_improving_trend_detected(self) -> None:
        evaluator = _make_long_evaluator()
        # first half: [0.4, 0.45]  mean = 0.425
        # last half:  [0.7, 0.75]  mean = 0.725
        # delta = 0.3 > 0.05 → IMPROVING
        for score in [0.4, 0.45, 0.7, 0.75]:
            evaluator.add_session(_make_session(f"s{score}", "op1", usefulness_score=score))
        trend = evaluator.evaluate_operator("op1")
        assert trend.usefulness_trend == "IMPROVING"

    def test_degrading_trend_detected(self) -> None:
        evaluator = _make_long_evaluator()
        # first half: [0.8, 0.75]  mean = 0.775
        # last half:  [0.4, 0.35]  mean = 0.375
        # delta = -0.4 < -0.05 → DEGRADING
        for score in [0.8, 0.75, 0.4, 0.35]:
            evaluator.add_session(_make_session(f"s{score}", "op1", usefulness_score=score))
        trend = evaluator.evaluate_operator("op1")
        assert trend.usefulness_trend == "DEGRADING"

    def test_stable_trend_detected_small_delta(self) -> None:
        evaluator = _make_long_evaluator()
        # first half: [0.6, 0.61] mean = 0.605
        # last half:  [0.62, 0.63] mean = 0.625
        # delta = 0.02 → STABLE
        for score in [0.60, 0.61, 0.62, 0.63]:
            evaluator.add_session(_make_session(f"s{score}", "op1", usefulness_score=score))
        trend = evaluator.evaluate_operator("op1")
        assert trend.usefulness_trend == "STABLE"

    def test_improving_trend_with_two_sessions(self) -> None:
        evaluator = _make_long_evaluator()
        # first half: [0.4], last half: [0.8] → delta=0.4 → IMPROVING
        evaluator.add_session(_make_session("s1", "op1", usefulness_score=0.4))
        evaluator.add_session(_make_session("s2", "op1", usefulness_score=0.8))
        trend = evaluator.evaluate_operator("op1")
        assert trend.usefulness_trend == "IMPROVING"

    def test_degrading_trend_with_two_sessions(self) -> None:
        evaluator = _make_long_evaluator()
        evaluator.add_session(_make_session("s1", "op1", usefulness_score=0.9))
        evaluator.add_session(_make_session("s2", "op1", usefulness_score=0.5))
        trend = evaluator.evaluate_operator("op1")
        assert trend.usefulness_trend == "DEGRADING"

    def test_exactly_0_05_delta_is_stable(self) -> None:
        # delta = 0.05 should be STABLE (threshold is strictly > 0.05)
        # Use exact fractions that don't accumulate float error: 0.60 - 0.55 = 0.05
        # but float arithmetic can produce 0.050...004, so use integer-representable values:
        # 0.5 and 0.6 → delta = 0.1 → IMPROVING; need exactly 0.05.
        # 4 sessions: first half [0.5,0.5] mean=0.5, last half [0.5,0.6] mean=0.55 → delta=0.05
        # 0.55 - 0.5 = 0.05 exactly in float? No — use 0.50 and 0.60:
        # first half [0.5, 0.6] mean=0.55, last half [0.55, 0.6] mean=0.575 → delta=0.025 → STABLE
        evaluator = _make_long_evaluator()
        # Craft delta = exactly 0.025 → clearly within ±0.05 stable band → STABLE
        for score in [0.5, 0.6, 0.55, 0.6]:
            evaluator.add_session(_make_session(f"s{score}", "op1", usefulness_score=score))
        trend = evaluator.evaluate_operator("op1")
        assert trend.usefulness_trend == "STABLE"

    # ---- Trust trend detection --------------------------------------------

    def test_trust_trend_improving(self) -> None:
        evaluator = _make_long_evaluator()
        evaluator.add_session(_make_session("s1", "op2", trust_at_end=0.3))
        evaluator.add_session(_make_session("s2", "op2", trust_at_end=0.9))
        trend = evaluator.evaluate_operator("op2")
        assert trend.trust_trend == "IMPROVING"

    def test_trust_trend_degrading(self) -> None:
        evaluator = _make_long_evaluator()
        evaluator.add_session(_make_session("s1", "op2", trust_at_end=0.9))
        evaluator.add_session(_make_session("s2", "op2", trust_at_end=0.3))
        trend = evaluator.evaluate_operator("op2")
        assert trend.trust_trend == "DEGRADING"

    def test_trust_trend_stable(self) -> None:
        evaluator = _make_long_evaluator()
        evaluator.add_session(_make_session("s1", "op2", trust_at_end=0.7))
        evaluator.add_session(_make_session("s2", "op2", trust_at_end=0.72))
        trend = evaluator.evaluate_operator("op2")
        assert trend.trust_trend == "STABLE"

    # ---- evaluate_all -----------------------------------------------------

    def test_evaluate_all_returns_only_operators_with_2_or_more_sessions(self) -> None:
        evaluator = _make_long_evaluator()
        # op-a: 2 sessions → included
        evaluator.add_session(_make_session("a1", "op-a"))
        evaluator.add_session(_make_session("a2", "op-a"))
        # op-b: 1 session → excluded
        evaluator.add_session(_make_session("b1", "op-b"))
        # op-c: 3 sessions → included
        evaluator.add_session(_make_session("c1", "op-c"))
        evaluator.add_session(_make_session("c2", "op-c"))
        evaluator.add_session(_make_session("c3", "op-c"))

        results = evaluator.evaluate_all()
        ids = {r.operator_id for r in results}
        assert "op-a" in ids
        assert "op-c" in ids
        assert "op-b" not in ids

    def test_evaluate_all_empty_when_no_operators(self) -> None:
        evaluator = _make_long_evaluator()
        assert evaluator.evaluate_all() == []

    def test_evaluate_all_returns_list_of_longitudinal_trends(self) -> None:
        evaluator = _make_long_evaluator()
        for i in range(3):
            evaluator.add_session(_make_session(f"s{i}", "op-x"))
        results = evaluator.evaluate_all()
        for item in results:
            assert isinstance(item, LongitudinalTrend)

    # ---- top_performers ---------------------------------------------------

    def test_top_performers_returns_n_results(self) -> None:
        evaluator = _make_long_evaluator()
        for op_id, score in [("op1", 0.9), ("op2", 0.7), ("op3", 0.5), ("op4", 0.3)]:
            evaluator.add_session(_make_session("s", op_id, usefulness_score=score))
        tops = evaluator.top_performers(n=2)
        assert len(tops) == 2

    def test_top_performers_sorted_by_mean_usefulness_desc(self) -> None:
        evaluator = _make_long_evaluator()
        for op_id, score in [("op1", 0.5), ("op2", 0.9), ("op3", 0.7)]:
            evaluator.add_session(_make_session("s", op_id, usefulness_score=score))
        tops = evaluator.top_performers(n=3)
        scores = [t.mean_usefulness for t in tops]
        assert scores == sorted(scores, reverse=True)

    def test_top_performers_best_is_first(self) -> None:
        evaluator = _make_long_evaluator()
        evaluator.add_session(_make_session("s1", "op-low", usefulness_score=0.4))
        evaluator.add_session(_make_session("s2", "op-high", usefulness_score=0.95))
        tops = evaluator.top_performers(n=1)
        assert len(tops) == 1
        assert tops[0].operator_id == "op-high"

    def test_top_performers_default_n_is_3(self) -> None:
        evaluator = _make_long_evaluator()
        for i in range(5):
            evaluator.add_session(_make_session(f"s{i}", f"op{i}", usefulness_score=0.5 + i * 0.1))
        tops = evaluator.top_performers()
        assert len(tops) == 3

    def test_top_performers_fewer_than_n_returns_all(self) -> None:
        evaluator = _make_long_evaluator()
        evaluator.add_session(_make_session("s1", "op1", usefulness_score=0.8))
        evaluator.add_session(_make_session("s2", "op2", usefulness_score=0.6))
        tops = evaluator.top_performers(n=5)
        assert len(tops) == 2

    # ---- Multiple operators independent -----------------------------------

    def test_multiple_operators_tracked_independently(self) -> None:
        evaluator = _make_long_evaluator()
        evaluator.add_session(_make_session("a1", "alice", usefulness_score=0.9))
        evaluator.add_session(_make_session("a2", "alice", usefulness_score=0.85))
        evaluator.add_session(_make_session("b1", "bob", usefulness_score=0.5))
        evaluator.add_session(_make_session("b2", "bob", usefulness_score=0.55))

        alice = evaluator.evaluate_operator("alice")
        bob = evaluator.evaluate_operator("bob")

        assert alice.mean_usefulness == pytest.approx(0.875)
        assert bob.mean_usefulness == pytest.approx(0.525)
        assert alice.session_count == 2
        assert bob.session_count == 2

    def test_session_order_preserved_for_trend(self) -> None:
        """Trend detection depends on insertion order."""
        evaluator = _make_long_evaluator()
        # Descending order → DEGRADING
        evaluator.add_session(_make_session("s1", "op1", usefulness_score=0.9))
        evaluator.add_session(_make_session("s2", "op1", usefulness_score=0.3))
        trend = evaluator.evaluate_operator("op1")
        assert trend.usefulness_trend == "DEGRADING"
