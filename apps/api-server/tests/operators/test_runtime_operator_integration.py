"""
Tests for Phase 49 Commit 7 — runtime_operator_integration.py

Covers:
  - OperatorRuntimeOrchestrator instantiation
  - assess_incident: boolean verdict derivation
  - compute_runtime_metrics: output field population
  - record_session_outcome + get_longitudinal_trend: end-to-end longitudinal eval
  - Vague recommendations → OPERATIONALLY_VAGUE → is_actionable_under_pressure=False
  - High fatigue → suppress_non_critical=True in runtime metrics
  - OperatorFacingAssessment field types (bool / float / str)
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))


from operators.workflow.actionability import ActionabilityClass
from operators.workflow.runtime_operator_integration import (
    OperatorFacingAssessment,
    OperatorRuntimeOrchestrator,
    RuntimeOperatorMetrics,
)

# ===========================================================================
# Shared fixtures and helpers
# ===========================================================================

# A well-formed, specific recommendation that produces a high actionability
# score (HIGHLY_ACTIONABLE or ACTIONABLE) and low friction.
_GOOD_REC = (
    "Step 1. Identify the affected pods: kubectl get pods -n production. "
    "Step 2. Check pod logs for OOM events: kubectl logs <pod> -n production. "
    "Step 3. When the issue is confirmed, restart the deployment: "
    "kubectl rollout restart deployment/api -n production. "
    "Step 4. Verify the rollout: kubectl rollout status deployment/api. "
    "Blast radius: all requests routed to the api deployment will experience "
    "a brief interruption (~30 seconds). "
    "Rollback: kubectl rollout undo deployment/api -n production."
)

_GOOD_NARRATIVE = (
    "The api deployment experienced an OOMKill event because the memory limit "
    "was set too low (ref-1). This caused a pod restart loop, resulting in "
    "increased error rates (ref-2). The root cause is a memory configuration "
    "misconfiguration triggered by the recent config change."
)

# A vague recommendation that exercises the OPERATIONALLY_VAGUE path.
_VAGUE_REC = (
    "Investigate further and check logs. Monitor the situation. "
    "Consider restarting the service if things don't improve. "
    "Look into the issue and may need to escalate."
)


def _make_orchestrator() -> OperatorRuntimeOrchestrator:
    return OperatorRuntimeOrchestrator()


# ---------------------------------------------------------------------------
# Default keyword arguments for assess_incident to keep tests DRY.
# ---------------------------------------------------------------------------
_BASE_ASSESS_KWARGS: dict = dict(
    operator_id="op-001",
    incident_id="inc-001",
    narrative=_GOOD_NARRATIVE,
    recommendation=_GOOD_REC,
    confidence=0.75,
    evidence_refs=["ref-1", "ref-2"],
    uncertainty_flags=["memory metrics incomplete"],
    contradictions=[],
    rollback_plan="kubectl rollout undo deployment/api -n production",
    dependencies=["database"],
    blast_radius_mentioned=True,
    escalation_reason=None,
    operator_fatigue=0.30,
    concurrent_incidents=1,
    trust_score=0.70,
)

# Default kwargs for compute_runtime_metrics.
_BASE_METRICS_KWARGS: dict = dict(
    operator_id="op-001",
    session_id="sess-001",
    recommendation_usefulness=0.70,
    escalation_density=2.0,
    override_count=1,
    total_recommendations=10,
    ambiguity_frequency=0.20,
    alert_noise_ratio=0.15,
    unresolved_pressure=0.30,
    active_ambiguity_count=2,
    alert_density=0.40,
    explanation_complexity=0.30,
    contradictory_signals=1,
    explanation_clarity=0.70,
    trust_score=0.65,
    workflow_quality=0.72,
    operator_alignment_score=0.68,
    escalation_burden=0.25,
    cognitive_load_val=0.30,
)


# ===========================================================================
# 1. Instantiation
# ===========================================================================


class TestInstantiation:
    def test_orchestrator_creates_all_sub_analyzers(self) -> None:
        orch = _make_orchestrator()
        assert orch.session_manager is not None
        assert orch.lifecycle_tracker is not None
        assert orch.escalation_chain is not None
        assert orch.explainability_analyzer is not None
        assert orch.rationale_validator is not None
        assert orch.consistency_checker is not None
        assert orch.actionability_analyzer is not None
        assert orch.usefulness_evaluator_rem is not None
        assert orch.friction_analyzer is not None
        assert orch.fatigue_model is not None
        assert orch.overload_detector is not None
        assert orch.escalation_fatigue_analyzer is not None
        assert orch.alignment_benchmark is not None
        assert orch.trust_model is not None
        assert orch.disagreement_analyzer is not None
        assert orch.workflow_benchmark is not None
        assert orch.usefulness_evaluator is not None
        assert orch.longitudinal_evaluator is not None

    def test_two_orchestrators_are_independent(self) -> None:
        orch_a = _make_orchestrator()
        orch_b = _make_orchestrator()
        # Record a session on orch_a only; orch_b should have no sessions.
        orch_a.record_session_outcome(
            operator_id="op-x",
            session_id="s1",
            usefulness_score=0.8,
            trust_at_end=0.7,
            incidents_handled=3,
            overrides=0,
            escalations=1,
        )
        trend_a = orch_a.get_longitudinal_trend("op-x")
        trend_b = orch_b.get_longitudinal_trend("op-x")
        assert trend_a.session_count == 1
        assert trend_b.session_count == 0


# ===========================================================================
# 2. assess_incident — boolean verdicts
# ===========================================================================


class TestAssessIncident:
    def test_returns_operator_facing_assessment(self) -> None:
        orch = _make_orchestrator()
        result = orch.assess_incident(**_BASE_ASSESS_KWARGS)
        assert isinstance(result, OperatorFacingAssessment)

    def test_incident_id_and_operator_id_propagated(self) -> None:
        orch = _make_orchestrator()
        result = orch.assess_incident(**_BASE_ASSESS_KWARGS)
        assert result.incident_id == "inc-001"
        assert result.operator_id == "op-001"

    # --- would_operator_trust ---

    def test_would_operator_trust_true_when_trust_and_explainability_high(self) -> None:
        orch = _make_orchestrator()
        result = orch.assess_incident(
            **{**_BASE_ASSESS_KWARGS, "trust_score": 0.80, "confidence": 0.65}
        )
        # With good narrative, evidence refs, and high trust we expect True.
        assert isinstance(result.would_operator_trust, bool)
        assert result.would_operator_trust is True

    def test_would_operator_trust_false_when_trust_score_low(self) -> None:
        orch = _make_orchestrator()
        result = orch.assess_incident(**{**_BASE_ASSESS_KWARGS, "trust_score": 0.40})
        assert result.would_operator_trust is False

    def test_would_operator_trust_false_when_explainability_low(self) -> None:
        # Vague causal language with no evidence → low explainability score.
        # "might ... possibly ... because of something" → causal claims without
        # evidence refs, plus vague modifiers → overall score drops below 0.55.
        orch = _make_orchestrator()
        result = orch.assess_incident(
            **{
                **_BASE_ASSESS_KWARGS,
                "trust_score": 0.80,
                "narrative": (
                    "The service might be degrading possibly because of something. "
                    "It could be a network issue or maybe a memory leak."
                ),
                "evidence_refs": [],
                "uncertainty_flags": [],
                "confidence": 0.95,
            }
        )
        # With no evidence, high confidence (honesty=0.20), and vague causal
        # language the overall explainability score is below 0.55 → False.
        assert result.would_operator_trust is False

    # --- would_reduce_burden ---

    def test_would_reduce_burden_true_when_low_fatigue_and_high_usefulness(self) -> None:
        orch = _make_orchestrator()
        result = orch.assess_incident(**{**_BASE_ASSESS_KWARGS, "operator_fatigue": 0.20})
        assert isinstance(result.would_reduce_burden, bool)
        # Low fatigue + good recommendation → should reduce burden
        assert result.would_reduce_burden is True

    def test_would_reduce_burden_false_when_fatigue_high(self) -> None:
        orch = _make_orchestrator()
        result = orch.assess_incident(**{**_BASE_ASSESS_KWARGS, "operator_fatigue": 0.80})
        assert result.would_reduce_burden is False

    def test_would_reduce_burden_false_when_usefulness_low(self) -> None:
        # Very brief recommendation → TOO_BRIEF → low usefulness score
        orch = _make_orchestrator()
        result = orch.assess_incident(
            **{
                **_BASE_ASSESS_KWARGS,
                "operator_fatigue": 0.20,
                "recommendation": "Check it.",
            }
        )
        # usefulness_score will be low (< 0.55) due to TOO_BRIEF penalty
        assert result.would_reduce_burden is False

    # --- is_actionable_under_pressure ---

    def test_is_actionable_under_pressure_true_for_good_recommendation(self) -> None:
        orch = _make_orchestrator()
        result = orch.assess_incident(**_BASE_ASSESS_KWARGS)
        assert isinstance(result.is_actionable_under_pressure, bool)
        # Good recommendation with low fatigue and low concurrent incidents
        assert result.is_actionable_under_pressure is True

    def test_is_actionable_under_pressure_false_for_vague_recommendation(self) -> None:
        orch = _make_orchestrator()
        result = orch.assess_incident(**{**_BASE_ASSESS_KWARGS, "recommendation": _VAGUE_REC})
        # Vague recommendation → OPERATIONALLY_VAGUE class → False
        assert result.is_actionable_under_pressure is False

    def test_is_actionable_under_pressure_false_when_friction_high(self) -> None:
        # Trigger high friction: very low confidence + high fatigue + many concurrent
        orch = _make_orchestrator()
        result = orch.assess_incident(
            **{
                **_BASE_ASSESS_KWARGS,
                "confidence": 0.10,  # LOW_CONFIDENCE friction +0.25
                "operator_fatigue": 0.90,  # HIGH_FATIGUE friction +0.20
                "concurrent_incidents": 3,  # CONCURRENT_INCIDENTS friction +0.30
                "recommendation": "Investigate further and check logs.",  # MISSING_ROLLBACK +0.15
            }
        )
        # Total friction > 0.70 → is_actionable_under_pressure = False
        assert result.is_actionable_under_pressure is False

    # --- Scalar field types ---

    def test_scalar_fields_are_float(self) -> None:
        orch = _make_orchestrator()
        result = orch.assess_incident(**_BASE_ASSESS_KWARGS)
        assert isinstance(result.recommendation_usefulness, float)
        assert isinstance(result.cognitive_load, float)
        assert isinstance(result.override_burden, float)
        assert isinstance(result.explanation_clarity, float)
        assert isinstance(result.trust_realism, float)

    def test_escalation_fatigue_risk_is_string(self) -> None:
        orch = _make_orchestrator()
        result = orch.assess_incident(**_BASE_ASSESS_KWARGS)
        assert isinstance(result.escalation_fatigue_risk, str)
        # Must be one of the EscalationFatigueRisk values
        valid_values = {"NONE", "LOW", "MODERATE", "HIGH", "SPAM"}
        assert result.escalation_fatigue_risk in valid_values

    def test_override_burden_is_zero_at_incident_level(self) -> None:
        # At incident assessment time there is no override history; must be 0.0
        orch = _make_orchestrator()
        result = orch.assess_incident(**_BASE_ASSESS_KWARGS)
        assert result.override_burden == 0.0

    def test_cognitive_load_equals_operator_fatigue(self) -> None:
        orch = _make_orchestrator()
        result = orch.assess_incident(**{**_BASE_ASSESS_KWARGS, "operator_fatigue": 0.45})
        assert result.cognitive_load == 0.45

    def test_trust_realism_equals_trust_score_input(self) -> None:
        orch = _make_orchestrator()
        result = orch.assess_incident(**{**_BASE_ASSESS_KWARGS, "trust_score": 0.72})
        assert result.trust_realism == 0.72

    def test_scalar_fields_in_unit_range(self) -> None:
        orch = _make_orchestrator()
        result = orch.assess_incident(**_BASE_ASSESS_KWARGS)
        for field_val in (
            result.recommendation_usefulness,
            result.cognitive_load,
            result.override_burden,
            result.explanation_clarity,
            result.trust_realism,
        ):
            assert 0.0 <= field_val <= 1.0, f"Out of [0,1]: {field_val}"

    def test_explanation_clarity_is_overall_explainability_score(self) -> None:
        orch = _make_orchestrator()
        result = orch.assess_incident(**_BASE_ASSESS_KWARGS)
        # explanation_clarity should match what ExplainabilityQualityAnalyzer returns
        exp = orch.explainability_analyzer.score(
            incident_id="inc-001",
            narrative=_GOOD_NARRATIVE,
            evidence_refs=["ref-1", "ref-2"],
            confidence=0.75,
            uncertainty_flags=["memory metrics incomplete"],
            contradictions=[],
        )
        assert result.explanation_clarity == exp.overall_explainability_score


# ===========================================================================
# 3. compute_runtime_metrics
# ===========================================================================


class TestComputeRuntimeMetrics:
    def test_returns_runtime_operator_metrics(self) -> None:
        orch = _make_orchestrator()
        result = orch.compute_runtime_metrics(**_BASE_METRICS_KWARGS)
        assert isinstance(result, RuntimeOperatorMetrics)

    def test_operator_id_and_session_id_propagated(self) -> None:
        orch = _make_orchestrator()
        result = orch.compute_runtime_metrics(**_BASE_METRICS_KWARGS)
        assert result.operator_id == "op-001"
        assert result.session_id == "sess-001"

    def test_all_fields_populated(self) -> None:
        orch = _make_orchestrator()
        result = orch.compute_runtime_metrics(**_BASE_METRICS_KWARGS)
        assert result.recommendation_usefulness == 0.70
        assert isinstance(result.escalation_fatigue_risk_level, str)
        assert isinstance(result.cognitive_load, float)
        assert isinstance(result.override_burden, float)
        assert isinstance(result.explanation_clarity, float)
        assert isinstance(result.trust_realism_score, float)
        assert isinstance(result.is_suppressing_non_critical, bool)
        assert isinstance(result.overall_operator_usefulness, float)

    def test_escalation_fatigue_risk_level_is_valid(self) -> None:
        orch = _make_orchestrator()
        result = orch.compute_runtime_metrics(**_BASE_METRICS_KWARGS)
        valid = {"NONE", "LOW", "MODERATE", "HIGH", "SPAM"}
        assert result.escalation_fatigue_risk_level in valid

    def test_cognitive_load_in_unit_range(self) -> None:
        orch = _make_orchestrator()
        result = orch.compute_runtime_metrics(**_BASE_METRICS_KWARGS)
        assert 0.0 <= result.cognitive_load <= 1.0

    def test_override_burden_computed_from_ratio(self) -> None:
        orch = _make_orchestrator()
        result = orch.compute_runtime_metrics(
            **{**_BASE_METRICS_KWARGS, "override_count": 3, "total_recommendations": 10}
        )
        assert abs(result.override_burden - 0.30) < 1e-9

    def test_override_burden_capped_at_one(self) -> None:
        orch = _make_orchestrator()
        result = orch.compute_runtime_metrics(
            **{**_BASE_METRICS_KWARGS, "override_count": 20, "total_recommendations": 5}
        )
        assert result.override_burden == 1.0

    def test_overall_operator_usefulness_in_unit_range(self) -> None:
        orch = _make_orchestrator()
        result = orch.compute_runtime_metrics(**_BASE_METRICS_KWARGS)
        assert 0.0 <= result.overall_operator_usefulness <= 1.0

    # --- High fatigue → suppress_non_critical=True ---

    def test_high_fatigue_triggers_suppress_non_critical(self) -> None:
        """
        When escalation_density is very high and other fatigue signals are
        elevated, FatigueModel classifies fatigue as HIGH or CRITICAL and
        sets suppress_non_critical=True.
        """
        orch = _make_orchestrator()
        # escalation_density=8 → normalised to 0.8 → contributes 0.25*0.8=0.20
        # override_burden=0.9 → contributes 0.20*0.9=0.18
        # ambiguity_frequency=0.9 → contributes 0.20*0.9=0.18
        # alert_noise_ratio=0.9 → contributes 0.20*0.9=0.18
        # unresolved_pressure=0.9 → contributes 0.15*0.9=0.135
        # total ≈ 0.875 → CRITICAL → suppress_non_critical=True
        result = orch.compute_runtime_metrics(
            **{
                **_BASE_METRICS_KWARGS,
                "escalation_density": 8.0,
                "override_count": 9,
                "total_recommendations": 10,  # override_burden=0.9
                "ambiguity_frequency": 0.90,
                "alert_noise_ratio": 0.90,
                "unresolved_pressure": 0.90,
            }
        )
        assert result.is_suppressing_non_critical is True

    def test_low_fatigue_does_not_suppress_non_critical(self) -> None:
        """
        Fresh operator with minimal signals → NOMINAL or ELEVATED → False.
        """
        orch = _make_orchestrator()
        result = orch.compute_runtime_metrics(
            **{
                **_BASE_METRICS_KWARGS,
                "escalation_density": 0.5,
                "override_count": 0,
                "total_recommendations": 10,
                "ambiguity_frequency": 0.05,
                "alert_noise_ratio": 0.05,
                "unresolved_pressure": 0.05,
            }
        )
        assert result.is_suppressing_non_critical is False

    def test_explanation_clarity_propagated(self) -> None:
        orch = _make_orchestrator()
        result = orch.compute_runtime_metrics(
            **{**_BASE_METRICS_KWARGS, "explanation_clarity": 0.88}
        )
        assert result.explanation_clarity == 0.88

    def test_trust_realism_score_propagated(self) -> None:
        orch = _make_orchestrator()
        result = orch.compute_runtime_metrics(**{**_BASE_METRICS_KWARGS, "trust_score": 0.55})
        assert result.trust_realism_score == 0.55

    def test_zero_total_recommendations_does_not_divide_by_zero(self) -> None:
        orch = _make_orchestrator()
        result = orch.compute_runtime_metrics(
            **{**_BASE_METRICS_KWARGS, "override_count": 5, "total_recommendations": 0}
        )
        assert result.override_burden == 1.0  # capped at 1.0


# ===========================================================================
# 4. record_session_outcome + get_longitudinal_trend
# ===========================================================================


class TestLongitudinalEvaluation:
    def test_single_session_recorded_and_retrieved(self) -> None:
        orch = _make_orchestrator()
        orch.record_session_outcome(
            operator_id="op-lon-01",
            session_id="s1",
            usefulness_score=0.75,
            trust_at_end=0.65,
            incidents_handled=5,
            overrides=1,
            escalations=2,
        )
        trend = orch.get_longitudinal_trend("op-lon-01")
        assert trend.session_count == 1
        assert abs(trend.mean_usefulness - 0.75) < 1e-9
        assert abs(trend.mean_trust - 0.65) < 1e-9
        assert trend.total_incidents == 5
        assert trend.total_overrides == 1
        assert trend.total_escalations == 2

    def test_unknown_operator_returns_empty_trend(self) -> None:
        orch = _make_orchestrator()
        trend = orch.get_longitudinal_trend("op-nonexistent")
        assert trend.session_count == 0
        assert trend.mean_usefulness == 0.0
        assert trend.mean_trust == 0.0

    def test_improving_usefulness_trend_detected(self) -> None:
        orch = _make_orchestrator()
        # Session 1 (low usefulness) → session 2 (high usefulness)
        orch.record_session_outcome(
            operator_id="op-lon-02",
            session_id="s1",
            usefulness_score=0.30,
            trust_at_end=0.50,
            incidents_handled=4,
            overrides=1,
            escalations=1,
        )
        orch.record_session_outcome(
            operator_id="op-lon-02",
            session_id="s2",
            usefulness_score=0.80,
            trust_at_end=0.70,
            incidents_handled=6,
            overrides=0,
            escalations=0,
        )
        trend = orch.get_longitudinal_trend("op-lon-02")
        assert trend.session_count == 2
        assert trend.usefulness_trend == "IMPROVING"

    def test_degrading_usefulness_trend_detected(self) -> None:
        orch = _make_orchestrator()
        orch.record_session_outcome(
            operator_id="op-lon-03",
            session_id="s1",
            usefulness_score=0.85,
            trust_at_end=0.75,
            incidents_handled=8,
            overrides=0,
            escalations=0,
        )
        orch.record_session_outcome(
            operator_id="op-lon-03",
            session_id="s2",
            usefulness_score=0.30,
            trust_at_end=0.40,
            incidents_handled=3,
            overrides=3,
            escalations=2,
        )
        trend = orch.get_longitudinal_trend("op-lon-03")
        assert trend.usefulness_trend == "DEGRADING"

    def test_stable_usefulness_trend_detected(self) -> None:
        orch = _make_orchestrator()
        for i in range(4):
            orch.record_session_outcome(
                operator_id="op-lon-04",
                session_id=f"s{i}",
                usefulness_score=0.65,
                trust_at_end=0.60,
                incidents_handled=5,
                overrides=1,
                escalations=1,
            )
        trend = orch.get_longitudinal_trend("op-lon-04")
        assert trend.usefulness_trend == "STABLE"

    def test_multi_session_aggregates_totals(self) -> None:
        orch = _make_orchestrator()
        sessions = [
            ("s1", 0.60, 0.55, 3, 1, 0),
            ("s2", 0.70, 0.60, 4, 0, 1),
            ("s3", 0.80, 0.70, 5, 2, 1),
        ]
        for session_id, u, t, inc, ov, esc in sessions:
            orch.record_session_outcome(
                operator_id="op-lon-05",
                session_id=session_id,
                usefulness_score=u,
                trust_at_end=t,
                incidents_handled=inc,
                overrides=ov,
                escalations=esc,
            )
        trend = orch.get_longitudinal_trend("op-lon-05")
        assert trend.session_count == 3
        assert trend.total_incidents == 12
        assert trend.total_overrides == 3
        assert trend.total_escalations == 2
        assert abs(trend.mean_usefulness - (0.60 + 0.70 + 0.80) / 3) < 1e-9

    def test_multiple_operators_tracked_independently(self) -> None:
        orch = _make_orchestrator()
        orch.record_session_outcome(
            operator_id="op-A",
            session_id="s1",
            usefulness_score=0.90,
            trust_at_end=0.85,
            incidents_handled=10,
            overrides=0,
            escalations=0,
        )
        orch.record_session_outcome(
            operator_id="op-B",
            session_id="s1",
            usefulness_score=0.40,
            trust_at_end=0.35,
            incidents_handled=2,
            overrides=5,
            escalations=3,
        )
        trend_a = orch.get_longitudinal_trend("op-A")
        trend_b = orch.get_longitudinal_trend("op-B")
        assert abs(trend_a.mean_usefulness - 0.90) < 1e-9
        assert abs(trend_b.mean_usefulness - 0.40) < 1e-9


# ===========================================================================
# 5. Vague recommendations lower actionability
# ===========================================================================


class TestVagueRecommendationActionability:
    def test_vague_recommendation_produces_vague_or_ambiguous_class(self) -> None:
        orch = _make_orchestrator()
        act_score = orch.actionability_analyzer.analyze(
            incident_id="inc-vague",
            recommendation=_VAGUE_REC,
            rollback_plan=None,
            dependencies=[],
            blast_radius_mentioned=False,
        )
        assert act_score.actionability_class in (
            ActionabilityClass.OPERATIONALLY_VAGUE,
            ActionabilityClass.DANGEROUSLY_AMBIGUOUS,
        )

    def test_vague_recommendation_sets_is_actionable_under_pressure_false(self) -> None:
        orch = _make_orchestrator()
        result = orch.assess_incident(
            **{
                **_BASE_ASSESS_KWARGS,
                "recommendation": _VAGUE_REC,
                "rollback_plan": None,
                "blast_radius_mentioned": False,
                "operator_fatigue": 0.20,  # keep fatigue low to isolate actionability
            }
        )
        assert result.is_actionable_under_pressure is False

    def test_actionable_recommendation_sets_is_actionable_under_pressure_true(self) -> None:
        orch = _make_orchestrator()
        result = orch.assess_incident(
            **{
                **_BASE_ASSESS_KWARGS,
                "recommendation": _GOOD_REC,
                "operator_fatigue": 0.20,
                "concurrent_incidents": 0,
                "confidence": 0.80,
            }
        )
        assert result.is_actionable_under_pressure is True

    def test_assessment_recommendation_usefulness_lower_for_vague(self) -> None:
        orch = _make_orchestrator()
        good_result = orch.assess_incident(**_BASE_ASSESS_KWARGS)
        vague_result = orch.assess_incident(**{**_BASE_ASSESS_KWARGS, "recommendation": _VAGUE_REC})
        assert vague_result.recommendation_usefulness < good_result.recommendation_usefulness


# ===========================================================================
# 6. OperatorFacingAssessment field type contract
# ===========================================================================


class TestAssessmentFieldTypes:
    def test_incident_id_and_operator_id_are_str(self) -> None:
        orch = _make_orchestrator()
        result = orch.assess_incident(**_BASE_ASSESS_KWARGS)
        assert isinstance(result.incident_id, str)
        assert isinstance(result.operator_id, str)

    def test_boolean_fields_are_bool_not_int(self) -> None:
        orch = _make_orchestrator()
        result = orch.assess_incident(**_BASE_ASSESS_KWARGS)
        # Python booleans are a subclass of int, but we validate they are bool
        # by checking type(x) is bool rather than isinstance(x, bool).
        assert type(result.would_operator_trust) is bool
        assert type(result.would_reduce_burden) is bool
        assert type(result.is_actionable_under_pressure) is bool

    def test_float_fields_are_float(self) -> None:
        orch = _make_orchestrator()
        result = orch.assess_incident(**_BASE_ASSESS_KWARGS)
        assert type(result.recommendation_usefulness) is float
        assert type(result.cognitive_load) is float
        assert type(result.override_burden) is float
        assert type(result.explanation_clarity) is float
        assert type(result.trust_realism) is float

    def test_escalation_fatigue_risk_is_str(self) -> None:
        orch = _make_orchestrator()
        result = orch.assess_incident(**_BASE_ASSESS_KWARGS)
        assert type(result.escalation_fatigue_risk) is str


# ===========================================================================
# 7. RuntimeOperatorMetrics field type contract
# ===========================================================================


class TestRuntimeMetricsFieldTypes:
    def test_operator_id_and_session_id_are_str(self) -> None:
        orch = _make_orchestrator()
        result = orch.compute_runtime_metrics(**_BASE_METRICS_KWARGS)
        assert isinstance(result.operator_id, str)
        assert isinstance(result.session_id, str)

    def test_is_suppressing_non_critical_is_bool(self) -> None:
        orch = _make_orchestrator()
        result = orch.compute_runtime_metrics(**_BASE_METRICS_KWARGS)
        assert type(result.is_suppressing_non_critical) is bool

    def test_numeric_fields_are_float(self) -> None:
        orch = _make_orchestrator()
        result = orch.compute_runtime_metrics(**_BASE_METRICS_KWARGS)
        for field_name, val in [
            ("recommendation_usefulness", result.recommendation_usefulness),
            ("cognitive_load", result.cognitive_load),
            ("override_burden", result.override_burden),
            ("explanation_clarity", result.explanation_clarity),
            ("trust_realism_score", result.trust_realism_score),
            ("overall_operator_usefulness", result.overall_operator_usefulness),
        ]:
            assert isinstance(val, float), f"{field_name} is not float: {type(val)}"

    def test_escalation_fatigue_risk_level_is_str(self) -> None:
        orch = _make_orchestrator()
        result = orch.compute_runtime_metrics(**_BASE_METRICS_KWARGS)
        assert isinstance(result.escalation_fatigue_risk_level, str)
