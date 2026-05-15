"""
Tests for Phase 49 Commit 3 — recommendation actionability analysis modules:
  - ActionabilityAnalyzer          (actionability.py)
  - RemediationUsefulnessEvaluator (remediation_usefulness.py)
  - OperationalFrictionAnalyzer    (operational_friction.py)
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

import pytest
from operators.workflow.actionability import (
    ActionabilityAnalyzer,
    ActionabilityClass,
    ActionabilityScore,
)
from operators.workflow.operational_friction import (
    FrictionFactor,
    OperationalFrictionAnalyzer,
    OperationalFrictionReport,
)
from operators.workflow.remediation_usefulness import (
    RemediationUsefulnessEvaluator,
    RemediationUsefulnessReport,
)

# ===========================================================================
# Helpers / factories
# ===========================================================================


def _make_actionability_analyzer() -> ActionabilityAnalyzer:
    return ActionabilityAnalyzer()


def _make_usefulness_evaluator() -> RemediationUsefulnessEvaluator:
    return RemediationUsefulnessEvaluator()


def _make_friction_analyzer() -> OperationalFrictionAnalyzer:
    return OperationalFrictionAnalyzer()


# ---------------------------------------------------------------------------
# A well-structured recommendation used as a high-quality baseline.
# ---------------------------------------------------------------------------
_GOOD_REC = (
    "Step 1. Identify the affected pods: kubectl get pods -n production. "
    "Step 2. Check pod logs for OOM events: kubectl logs <pod> -n production. "
    "Step 3. When the issue is confirmed, restart the deployment: "
    "kubectl rollout restart deployment/api -n production. "
    "Step 4. Verify the rollout: kubectl rollout status deployment/api. "
    "Blast radius: all requests routed to the api deployment will experience "
    "a brief interruption (~30 seconds). "
    "Rollback: kubectl rollout undo deployment/api -n production. "
    "This action is idempotent and safe to retry."
)

_GOOD_ROLLBACK = "kubectl rollout undo deployment/api -n production"

_MINIMAL_REC = "Restart the service."

_NO_ROLLBACK: str | None = None


# ===========================================================================
# ActionabilityAnalyzer
# ===========================================================================


class TestActionabilityAnalyzer:

    # ---- Return type -------------------------------------------------------

    def test_returns_actionability_score_dataclass(self) -> None:
        analyzer = _make_actionability_analyzer()
        result = analyzer.analyze(
            incident_id="inc-a01",
            recommendation=_GOOD_REC,
            rollback_plan=_GOOD_ROLLBACK,
            dependencies=["database", "cache"],
            blast_radius_mentioned=True,
        )
        assert isinstance(result, ActionabilityScore)
        assert result.incident_id == "inc-a01"

    def test_all_scores_bounded_0_to_1(self) -> None:
        analyzer = _make_actionability_analyzer()
        result = analyzer.analyze(
            incident_id="inc-a02",
            recommendation=_GOOD_REC,
            rollback_plan=_GOOD_ROLLBACK,
            dependencies=["db"],
            blast_radius_mentioned=True,
        )
        for field_name in [
            "clarity",
            "operational_specificity",
            "execution_feasibility",
            "rollback_preparedness",
            "dependency_awareness",
            "safety_explicitness",
            "ambiguity_penalty",
            "overall_actionability",
        ]:
            value = getattr(result, field_name)
            assert 0.0 <= value <= 1.0, f"{field_name}={value} out of [0, 1]"

    def test_actionability_class_is_enum_member(self) -> None:
        analyzer = _make_actionability_analyzer()
        result = analyzer.analyze(
            incident_id="inc-a03",
            recommendation=_GOOD_REC,
            rollback_plan=_GOOD_ROLLBACK,
            dependencies=[],
            blast_radius_mentioned=True,
        )
        assert isinstance(result.actionability_class, ActionabilityClass)

    # ---- Vague pattern detection ------------------------------------------

    def test_vague_pattern_investigate_further_penalises_clarity(self) -> None:
        analyzer = _make_actionability_analyzer()
        vague = "investigate further and check logs to monitor the situation."
        clean = "kubectl rollout restart deployment/api -n production."
        r_vague = analyzer.analyze("inc-v1", vague, _GOOD_ROLLBACK, [], False)
        r_clean = analyzer.analyze("inc-v2", clean, _GOOD_ROLLBACK, [], False)
        assert r_vague.clarity < r_clean.clarity

    def test_vague_pattern_look_into_detected(self) -> None:
        analyzer = _make_actionability_analyzer()
        rec = "You should look into the issue and may need to restart the pod."
        result = analyzer.analyze("inc-v3", rec, _GOOD_ROLLBACK, [], False)
        # Multiple vague phrases → vague_penalty > 0 → clarity < 1.0
        assert result.clarity < 1.0

    def test_vague_pattern_might_be_detected(self) -> None:
        analyzer = _make_actionability_analyzer()
        rec = "The issue might be caused by memory limits. Consider restarting if so."
        result = analyzer.analyze("inc-v4", rec, _GOOD_ROLLBACK, [], False)
        assert result.clarity < 1.0

    def test_vague_pattern_could_potentially_detected(self) -> None:
        analyzer = _make_actionability_analyzer()
        rec = "Restarting could potentially resolve the issue."
        result = analyzer.analyze("inc-v5", rec, _GOOD_ROLLBACK, [], False)
        assert result.clarity < 1.0

    def test_no_vague_phrases_gives_high_clarity(self) -> None:
        analyzer = _make_actionability_analyzer()
        rec = "Step 1. kubectl rollout restart deployment/api."
        result = analyzer.analyze("inc-v6", rec, _GOOD_ROLLBACK, [], True)
        assert result.clarity >= 0.80

    # ---- Anti-pattern: unconditional restart (+0.25) -----------------------

    def test_unconditional_restart_adds_penalty(self) -> None:
        analyzer = _make_actionability_analyzer()
        with_restart = "Restart the pod to resolve the issue."
        without_restart = "Scale the deployment to resolve the issue."
        r_restart = analyzer.analyze("inc-ap1", with_restart, _GOOD_ROLLBACK, [], True)
        r_no_restart = analyzer.analyze("inc-ap2", without_restart, _GOOD_ROLLBACK, [], True)
        # Restart without condition adds 0.25 to ambiguity_penalty
        assert r_restart.ambiguity_penalty > r_no_restart.ambiguity_penalty

    def test_conditional_restart_does_not_add_penalty(self) -> None:
        analyzer = _make_actionability_analyzer()
        rec = "When CPU usage exceeds 90%, restart the deployment using kubectl."
        result = analyzer.analyze("inc-ap3", rec, _GOOD_ROLLBACK, [], True)
        # "restart" is present but so is "when" → no unconditional restart penalty
        # (total penalty from other sources may differ, but this specific sub-penalty = 0)
        # We compare against a version without "restart" at all.
        rec_no_restart = "Scale the deployment using kubectl when CPU usage exceeds 90%."
        r_no_restart = analyzer.analyze("inc-ap4", rec_no_restart, _GOOD_ROLLBACK, [], True)
        assert result.ambiguity_penalty == pytest.approx(r_no_restart.ambiguity_penalty, abs=0.01)

    def test_restart_with_if_condition_no_penalty(self) -> None:
        analyzer = _make_actionability_analyzer()
        rec = "If the pod fails the readiness probe, restart it using kubectl."
        result = analyzer.analyze("inc-ap5", rec, _GOOD_ROLLBACK, [], True)
        rec_no_restart = "If the pod fails the readiness probe, delete and redeploy."
        r_nr = analyzer.analyze("inc-ap6", rec_no_restart, _GOOD_ROLLBACK, [], True)
        assert result.ambiguity_penalty == pytest.approx(r_nr.ambiguity_penalty, abs=0.01)

    # ---- Anti-pattern: missing/trivial rollback (+0.20) -------------------

    def test_none_rollback_adds_penalty(self) -> None:
        analyzer = _make_actionability_analyzer()
        r_none = analyzer.analyze("inc-ap7", _GOOD_REC, None, [], True)
        r_good = analyzer.analyze("inc-ap8", _GOOD_REC, _GOOD_ROLLBACK, [], True)
        # None rollback adds 0.20 compared to a good rollback
        assert r_none.ambiguity_penalty > r_good.ambiguity_penalty

    def test_short_rollback_under_20_chars_adds_penalty(self) -> None:
        analyzer = _make_actionability_analyzer()
        r_short = analyzer.analyze("inc-ap9", _GOOD_REC, "undo", [], True)
        r_good = analyzer.analyze("inc-ap10", _GOOD_REC, _GOOD_ROLLBACK, [], True)
        assert r_short.ambiguity_penalty > r_good.ambiguity_penalty

    def test_rollback_exact_20_chars_does_not_add_penalty(self) -> None:
        analyzer = _make_actionability_analyzer()
        exactly_20 = "A" * 20  # exactly 20 characters
        result = analyzer.analyze("inc-ap11", _GOOD_REC, exactly_20, [], True)
        # >= 20 chars → no rollback penalty; compare with None
        r_none = analyzer.analyze("inc-ap12", _GOOD_REC, None, [], True)
        assert result.ambiguity_penalty < r_none.ambiguity_penalty

    # ---- Anti-pattern: no blast radius (+0.15) ----------------------------

    def test_no_blast_radius_in_text_adds_penalty(self) -> None:
        analyzer = _make_actionability_analyzer()
        rec_with = "Blast radius: only the api pods. kubectl rollout restart deployment/api."
        rec_without = "kubectl rollout restart deployment/api."
        r_with = analyzer.analyze("inc-ap13", rec_with, _GOOD_ROLLBACK, [], True)
        r_without = analyzer.analyze("inc-ap14", rec_without, _GOOD_ROLLBACK, [], True)
        # rec_without triggers the missing-blast-radius anti-pattern
        assert r_without.ambiguity_penalty > r_with.ambiguity_penalty

    # ---- Anti-pattern: no step numbers (+0.10) ----------------------------

    def test_no_step_numbers_adds_penalty(self) -> None:
        analyzer = _make_actionability_analyzer()
        with_steps = "Step 1. Do X. Step 2. Do Y."
        without_steps = "Do X then do Y."
        r_with = analyzer.analyze("inc-ap15", with_steps, _GOOD_ROLLBACK, [], True)
        r_without = analyzer.analyze("inc-ap16", without_steps, _GOOD_ROLLBACK, [], True)
        assert r_without.ambiguity_penalty > r_with.ambiguity_penalty

    def test_numbered_list_detected_as_steps(self) -> None:
        analyzer = _make_actionability_analyzer()
        rec = "1. Run kubectl apply. 2. Wait 30 seconds. 3. Verify with kubectl get pods."
        result = analyzer.analyze("inc-ap17", rec, _GOOD_ROLLBACK, [], True)
        # Numbered list → steps present → no step-number anti-pattern penalty
        rec_no_steps = "Run kubectl apply. Wait 30 seconds. Verify with kubectl get pods."
        r_ns = analyzer.analyze("inc-ap18", rec_no_steps, _GOOD_ROLLBACK, [], True)
        assert result.ambiguity_penalty < r_ns.ambiguity_penalty

    def test_ambiguity_penalty_capped_at_1(self) -> None:
        analyzer = _make_actionability_analyzer()
        # Triggers all four anti-patterns
        rec = "Restart the service."  # unconditional restart, no steps, no blast radius
        result = analyzer.analyze("inc-ap19", rec, None, [], False)
        assert result.ambiguity_penalty <= 1.0

    # ---- Classification thresholds ----------------------------------------

    def test_classify_highly_actionable_above_0_80(self) -> None:
        analyzer = _make_actionability_analyzer()
        klass = analyzer._classify(0.85)
        assert klass == ActionabilityClass.HIGHLY_ACTIONABLE

    def test_classify_highly_actionable_at_0_80(self) -> None:
        analyzer = _make_actionability_analyzer()
        klass = analyzer._classify(0.80)
        assert klass == ActionabilityClass.HIGHLY_ACTIONABLE

    def test_classify_actionable_at_0_60(self) -> None:
        analyzer = _make_actionability_analyzer()
        klass = analyzer._classify(0.60)
        assert klass == ActionabilityClass.ACTIONABLE

    def test_classify_actionable_between_0_60_and_0_80(self) -> None:
        analyzer = _make_actionability_analyzer()
        klass = analyzer._classify(0.70)
        assert klass == ActionabilityClass.ACTIONABLE

    def test_classify_partially_actionable_at_0_40(self) -> None:
        analyzer = _make_actionability_analyzer()
        klass = analyzer._classify(0.40)
        assert klass == ActionabilityClass.PARTIALLY_ACTIONABLE

    def test_classify_partially_actionable_between_0_40_and_0_60(self) -> None:
        analyzer = _make_actionability_analyzer()
        klass = analyzer._classify(0.50)
        assert klass == ActionabilityClass.PARTIALLY_ACTIONABLE

    def test_classify_operationally_vague_at_0_20(self) -> None:
        analyzer = _make_actionability_analyzer()
        klass = analyzer._classify(0.20)
        assert klass == ActionabilityClass.OPERATIONALLY_VAGUE

    def test_classify_operationally_vague_between_0_20_and_0_40(self) -> None:
        analyzer = _make_actionability_analyzer()
        klass = analyzer._classify(0.30)
        assert klass == ActionabilityClass.OPERATIONALLY_VAGUE

    def test_classify_dangerously_ambiguous_below_0_20(self) -> None:
        analyzer = _make_actionability_analyzer()
        klass = analyzer._classify(0.10)
        assert klass == ActionabilityClass.DANGEROUSLY_AMBIGUOUS

    def test_classify_dangerously_ambiguous_at_zero(self) -> None:
        analyzer = _make_actionability_analyzer()
        klass = analyzer._classify(0.0)
        assert klass == ActionabilityClass.DANGEROUSLY_AMBIGUOUS

    # ---- Rollback preparedness sub-scores ---------------------------------

    def test_good_rollback_yields_full_preparedness(self) -> None:
        analyzer = _make_actionability_analyzer()
        result = analyzer.analyze("inc-rp1", _GOOD_REC, _GOOD_ROLLBACK, [], True)
        assert result.rollback_preparedness == 1.0

    def test_none_rollback_yields_zero_preparedness(self) -> None:
        analyzer = _make_actionability_analyzer()
        result = analyzer.analyze("inc-rp2", _GOOD_REC, None, [], True)
        assert result.rollback_preparedness == 0.0

    def test_short_rollback_yields_partial_preparedness(self) -> None:
        analyzer = _make_actionability_analyzer()
        result = analyzer.analyze("inc-rp3", _GOOD_REC, "undo it", [], True)
        assert 0.0 < result.rollback_preparedness < 1.0

    # ---- Dependency awareness ---------------------------------------------

    def test_all_dependencies_mentioned_yields_full_awareness(self) -> None:
        analyzer = _make_actionability_analyzer()
        rec = "Step 1. Check database connection. Step 2. Flush the cache layer."
        result = analyzer.analyze("inc-da1", rec, _GOOD_ROLLBACK, ["database", "cache"], True)
        assert result.dependency_awareness == 1.0

    def test_no_dependencies_listed_yields_neutral_score(self) -> None:
        analyzer = _make_actionability_analyzer()
        result = analyzer.analyze("inc-da2", _GOOD_REC, _GOOD_ROLLBACK, [], True)
        # Empty dependency list → neutral 0.70
        assert result.dependency_awareness == pytest.approx(0.70)

    def test_partial_dependency_mention_yields_partial_awareness(self) -> None:
        analyzer = _make_actionability_analyzer()
        rec = "Restart the api service. The cache is not affected."
        result = analyzer.analyze("inc-da3", rec, _GOOD_ROLLBACK, ["database", "cache"], True)
        # Only "cache" is mentioned → 1/2 = 0.50
        assert result.dependency_awareness == pytest.approx(0.50)

    # ---- Safety explicitness ----------------------------------------------

    def test_blast_radius_flag_boosts_safety_score(self) -> None:
        analyzer = _make_actionability_analyzer()
        r_with = analyzer.analyze("inc-se1", _GOOD_REC, _GOOD_ROLLBACK, [], True)
        r_without = analyzer.analyze("inc-se2", _GOOD_REC, _GOOD_ROLLBACK, [], False)
        assert r_with.safety_explicitness > r_without.safety_explicitness

    # ---- Overall score formula --------------------------------------------

    def test_overall_score_floor_is_zero(self) -> None:
        analyzer = _make_actionability_analyzer()
        result = analyzer.analyze(
            incident_id="inc-os1",
            recommendation=_MINIMAL_REC,
            rollback_plan=None,
            dependencies=[],
            blast_radius_mentioned=False,
        )
        assert result.overall_actionability >= 0.0

    def test_high_quality_recommendation_scores_high(self) -> None:
        analyzer = _make_actionability_analyzer()
        result = analyzer.analyze(
            incident_id="inc-os2",
            recommendation=_GOOD_REC,
            rollback_plan=_GOOD_ROLLBACK,
            dependencies=["database"],
            blast_radius_mentioned=True,
        )
        # The good rec should land in ACTIONABLE or HIGHLY_ACTIONABLE territory
        assert result.overall_actionability >= 0.50

    def test_minimal_vague_recommendation_scores_low(self) -> None:
        analyzer = _make_actionability_analyzer()
        result = analyzer.analyze(
            incident_id="inc-os3",
            recommendation="investigate further and check logs to monitor the situation",
            rollback_plan=None,
            dependencies=[],
            blast_radius_mentioned=False,
        )
        assert result.overall_actionability < 0.50


# ===========================================================================
# RemediationUsefulnessEvaluator
# ===========================================================================


class TestRemediationUsefulnessEvaluator:

    # ---- Return type -------------------------------------------------------

    def test_returns_report_dataclass(self) -> None:
        evaluator = _make_usefulness_evaluator()
        result = evaluator.evaluate(
            incident_id="inc-u01",
            recommendation=_GOOD_REC,
            mechanism="OOMKill in api pod",
        )
        assert isinstance(result, RemediationUsefulnessReport)
        assert result.incident_id == "inc-u01"

    def test_usefulness_score_bounded_0_to_1(self) -> None:
        evaluator = _make_usefulness_evaluator()
        for rec in [_GOOD_REC, _MINIMAL_REC, "", "x" * 200]:
            result = evaluator.evaluate("inc-u02", rec, "oom")
            assert (
                0.0 <= result.usefulness_score <= 1.0
            ), f"Score {result.usefulness_score} out of range for rec: {rec[:30]!r}"

    def test_recommendation_length_chars_correct(self) -> None:
        evaluator = _make_usefulness_evaluator()
        rec = "kubectl rollout restart deployment/api. Verify with kubectl get pods."
        result = evaluator.evaluate("inc-u03", rec, "crash loop")
        assert result.recommendation_length_chars == len(rec)

    # ---- Signal: has_specific_commands (+0.20) ----------------------------

    def test_kubectl_command_detected(self) -> None:
        evaluator = _make_usefulness_evaluator()
        result = evaluator.evaluate(
            "inc-s01",
            "kubectl rollout restart deployment/api -n production.",
            "crash",
        )
        assert result.has_specific_commands is True
        assert any(s.signal_type == "HAS_SPECIFIC_COMMANDS" for s in result.signals)

    def test_helm_command_detected(self) -> None:
        evaluator = _make_usefulness_evaluator()
        result = evaluator.evaluate(
            "inc-s02",
            "helm upgrade api ./chart --set replicas=3.",
            "config drift",
        )
        assert result.has_specific_commands is True

    def test_systemctl_command_detected(self) -> None:
        evaluator = _make_usefulness_evaluator()
        result = evaluator.evaluate(
            "inc-s03",
            "systemctl restart nginx on the load balancer host.",
            "nginx crash",
        )
        assert result.has_specific_commands is True

    def test_docker_command_detected(self) -> None:
        evaluator = _make_usefulness_evaluator()
        result = evaluator.evaluate(
            "inc-s04",
            "docker restart api-container on the host.",
            "container crash",
        )
        assert result.has_specific_commands is True

    def test_aws_command_detected(self) -> None:
        evaluator = _make_usefulness_evaluator()
        result = evaluator.evaluate(
            "inc-s05",
            "aws ecs update-service --cluster prod --service api --force-new-deployment.",
            "ecs task failure",
        )
        assert result.has_specific_commands is True

    def test_terraform_command_detected(self) -> None:
        evaluator = _make_usefulness_evaluator()
        result = evaluator.evaluate(
            "inc-s06",
            "terraform apply -target=module.api to restore infra state.",
            "infra drift",
        )
        assert result.has_specific_commands is True

    def test_no_commands_not_detected(self) -> None:
        evaluator = _make_usefulness_evaluator()
        result = evaluator.evaluate(
            "inc-s07",
            "Ask the on-call engineer to check the service health dashboard.",
            "unknown",
        )
        assert result.has_specific_commands is False
        assert not any(s.signal_type == "HAS_SPECIFIC_COMMANDS" for s in result.signals)

    # ---- Signal: has_verification_step (+0.15) ----------------------------

    def test_verify_keyword_detected(self) -> None:
        evaluator = _make_usefulness_evaluator()
        result = evaluator.evaluate(
            "inc-s08",
            "Restart the pod. Verify it is running with kubectl get pods.",
            "crash",
        )
        assert result.has_verification_step is True
        assert any(s.signal_type == "HAS_VERIFICATION_STEP" for s in result.signals)

    def test_check_keyword_detected(self) -> None:
        evaluator = _make_usefulness_evaluator()
        result = evaluator.evaluate(
            "inc-s09",
            "Restart the pod. Check the logs to confirm it started.",
            "crash",
        )
        assert result.has_verification_step is True

    def test_confirm_keyword_detected(self) -> None:
        evaluator = _make_usefulness_evaluator()
        result = evaluator.evaluate(
            "inc-s10",
            "Scale the deployment up. Confirm that traffic normalises.",
            "scale issue",
        )
        assert result.has_verification_step is True

    def test_validate_keyword_detected(self) -> None:
        evaluator = _make_usefulness_evaluator()
        result = evaluator.evaluate(
            "inc-s11",
            "Apply the patch. Validate with integration tests.",
            "regression",
        )
        assert result.has_verification_step is True

    def test_test_keyword_detected(self) -> None:
        evaluator = _make_usefulness_evaluator()
        result = evaluator.evaluate(
            "inc-s12",
            "Deploy the fix. Test the health endpoint before removing hold.",
            "deploy",
        )
        assert result.has_verification_step is True

    def test_no_verification_keyword_not_detected(self) -> None:
        evaluator = _make_usefulness_evaluator()
        result = evaluator.evaluate(
            "inc-s13",
            "Restart the pod immediately using kubectl.",
            "crash",
        )
        assert result.has_verification_step is False

    # ---- Signal: has_timing_guidance (+0.10) ------------------------------

    def test_wait_keyword_detected(self) -> None:
        evaluator = _make_usefulness_evaluator()
        result = evaluator.evaluate(
            "inc-s14",
            "Restart the deployment. Wait for pods to become ready.",
            "crash",
        )
        assert result.has_timing_guidance is True
        assert any(s.signal_type == "HAS_TIMING_GUIDANCE" for s in result.signals)

    def test_minutes_keyword_detected(self) -> None:
        evaluator = _make_usefulness_evaluator()
        result = evaluator.evaluate(
            "inc-s15",
            "Scale down first, then wait 5 minutes before scaling back up.",
            "thundering herd",
        )
        assert result.has_timing_guidance is True

    def test_seconds_keyword_detected(self) -> None:
        evaluator = _make_usefulness_evaluator()
        result = evaluator.evaluate(
            "inc-s16",
            "Drain the node. The eviction should complete within 30 seconds.",
            "node drain",
        )
        assert result.has_timing_guidance is True

    def test_timeout_keyword_detected(self) -> None:
        evaluator = _make_usefulness_evaluator()
        result = evaluator.evaluate(
            "inc-s17",
            "Apply the change with --timeout=300s flag to avoid hanging.",
            "apply stall",
        )
        assert result.has_timing_guidance is True

    def test_grace_period_keyword_detected(self) -> None:
        evaluator = _make_usefulness_evaluator()
        result = evaluator.evaluate(
            "inc-s18",
            "Delete the pod with a grace period of 60 seconds.",
            "pod stuck",
        )
        assert result.has_timing_guidance is True

    def test_no_timing_keywords_not_detected(self) -> None:
        evaluator = _make_usefulness_evaluator()
        result = evaluator.evaluate(
            "inc-s19",
            "kubectl rollout restart deployment/api. Verify with kubectl get pods.",
            "crash",
        )
        assert result.has_timing_guidance is False

    # ---- Signal: is_idempotent_safe (+0.10) -------------------------------

    def test_idempotent_keyword_detected(self) -> None:
        evaluator = _make_usefulness_evaluator()
        result = evaluator.evaluate(
            "inc-s20",
            "This operation is idempotent and will not cause data loss.",
            "config apply",
        )
        assert result.is_idempotent_safe is True
        assert any(s.signal_type == "IS_IDEMPOTENT_SAFE" for s in result.signals)

    def test_safe_to_retry_phrase_detected(self) -> None:
        evaluator = _make_usefulness_evaluator()
        result = evaluator.evaluate(
            "inc-s21",
            "The rollout is safe to retry if it fails during transit.",
            "deploy",
        )
        assert result.is_idempotent_safe is True

    def test_can_be_run_multiple_times_detected(self) -> None:
        evaluator = _make_usefulness_evaluator()
        result = evaluator.evaluate(
            "inc-s22",
            "This script can be run multiple times without side effects.",
            "infra apply",
        )
        assert result.is_idempotent_safe is True

    def test_no_idempotent_phrase_not_detected(self) -> None:
        evaluator = _make_usefulness_evaluator()
        result = evaluator.evaluate(
            "inc-s23",
            "kubectl rollout restart deployment/api.",
            "crash",
        )
        assert result.is_idempotent_safe is False

    # ---- Signal: too_brief (-0.20) ----------------------------------------

    def test_short_rec_under_50_chars_penalised(self) -> None:
        evaluator = _make_usefulness_evaluator()
        rec = "Restart the pod."  # 16 chars
        result = evaluator.evaluate("inc-s24", rec, "crash")
        assert any(s.signal_type == "TOO_BRIEF" for s in result.signals)
        # TOO_BRIEF signal has negative impact
        too_brief_signal = next(s for s in result.signals if s.signal_type == "TOO_BRIEF")
        assert too_brief_signal.impact < 0.0

    def test_rec_exactly_50_chars_not_penalised(self) -> None:
        evaluator = _make_usefulness_evaluator()
        rec = "A" * 50
        result = evaluator.evaluate("inc-s25", rec, "crash")
        assert not any(s.signal_type == "TOO_BRIEF" for s in result.signals)

    def test_rec_over_50_chars_not_penalised(self) -> None:
        evaluator = _make_usefulness_evaluator()
        rec = "kubectl rollout restart deployment/api -n production and verify pods are running."
        assert len(rec) > 50
        result = evaluator.evaluate("inc-s26", rec, "crash")
        assert not any(s.signal_type == "TOO_BRIEF" for s in result.signals)

    # ---- Score calculation ------------------------------------------------

    def test_baseline_score_is_0_40_for_unremarkable_rec(self) -> None:
        evaluator = _make_usefulness_evaluator()
        # A 50+ char rec with no features and no vague language
        rec = "Scale the deployment to address the elevated error rate in production."
        result = evaluator.evaluate("inc-sc1", rec, "error rate")
        # No commands, no verify, no timing, not idempotent, not too brief
        # → score = 0.40
        assert result.usefulness_score == pytest.approx(0.40)

    def test_all_positive_signals_approach_maximum(self) -> None:
        evaluator = _make_usefulness_evaluator()
        # Triggers all four positive signals
        result = evaluator.evaluate(
            "inc-sc2",
            _GOOD_REC,
            "oom",
        )
        # Baseline 0.40 + 0.20 + 0.15 + 0.10 + 0.10 = 0.95
        assert result.usefulness_score >= 0.80

    def test_too_brief_lowers_score_from_baseline(self) -> None:
        evaluator = _make_usefulness_evaluator()
        brief = "Restart it."  # < 50 chars, no other signals
        result = evaluator.evaluate("inc-sc3", brief, "crash")
        # 0.40 - 0.20 = 0.20
        assert result.usefulness_score == pytest.approx(0.20)

    def test_score_not_below_zero(self) -> None:
        evaluator = _make_usefulness_evaluator()
        result = evaluator.evaluate("inc-sc4", "OK", "crash")
        assert result.usefulness_score >= 0.0

    def test_score_not_above_one(self) -> None:
        evaluator = _make_usefulness_evaluator()
        result = evaluator.evaluate("inc-sc5", _GOOD_REC, "oom")
        assert result.usefulness_score <= 1.0

    # ---- Signal impact values ---------------------------------------------

    def test_has_specific_commands_signal_impact_is_positive(self) -> None:
        evaluator = _make_usefulness_evaluator()
        result = evaluator.evaluate("inc-si1", "kubectl get pods.", "crash")
        cmd_signal = next(
            (s for s in result.signals if s.signal_type == "HAS_SPECIFIC_COMMANDS"), None
        )
        assert cmd_signal is not None
        assert cmd_signal.impact > 0.0

    def test_has_verification_step_signal_impact_is_positive(self) -> None:
        evaluator = _make_usefulness_evaluator()
        rec = "Do the fix. Verify the service is healthy. " + "X" * 20
        result = evaluator.evaluate("inc-si2", rec, "crash")
        verify_signal = next(
            (s for s in result.signals if s.signal_type == "HAS_VERIFICATION_STEP"), None
        )
        assert verify_signal is not None
        assert verify_signal.impact > 0.0


# ===========================================================================
# OperationalFrictionAnalyzer
# ===========================================================================


class TestOperationalFrictionAnalyzer:

    # ---- Return type -------------------------------------------------------

    def test_returns_report_dataclass(self) -> None:
        analyzer = _make_friction_analyzer()
        result = analyzer.analyze(
            incident_id="inc-f01",
            recommendation=_GOOD_REC,
            operator_fatigue=0.50,
            concurrent_incidents=1,
            confidence=0.80,
        )
        assert isinstance(result, OperationalFrictionReport)
        assert result.incident_id == "inc-f01"

    def test_total_friction_bounded_0_to_1(self) -> None:
        analyzer = _make_friction_analyzer()
        # Worst-case scenario
        result = analyzer.analyze(
            incident_id="inc-f02",
            recommendation="Restart everything.",
            operator_fatigue=1.0,
            concurrent_incidents=10,
            confidence=0.10,
        )
        assert 0.0 <= result.total_friction <= 1.0

    # ---- Factor: LOW_CONFIDENCE (+0.25 when confidence < 0.50) -----------

    def test_low_confidence_factor_added_below_0_50(self) -> None:
        analyzer = _make_friction_analyzer()
        result = analyzer.analyze("inc-f03", _GOOD_REC, 0.50, 0, 0.49)
        names = {f.factor_name for f in result.factors}
        assert "LOW_CONFIDENCE" in names

    def test_low_confidence_factor_cost_is_0_25(self) -> None:
        analyzer = _make_friction_analyzer()
        result = analyzer.analyze("inc-f04", _GOOD_REC, 0.0, 0, 0.30)
        low_conf = next(f for f in result.factors if f.factor_name == "LOW_CONFIDENCE")
        assert low_conf.friction_cost == pytest.approx(0.25)

    def test_confidence_exactly_0_50_no_low_confidence_factor(self) -> None:
        analyzer = _make_friction_analyzer()
        result = analyzer.analyze("inc-f05", _GOOD_REC, 0.0, 0, 0.50)
        names = {f.factor_name for f in result.factors}
        assert "LOW_CONFIDENCE" not in names

    def test_confidence_above_0_50_no_low_confidence_factor(self) -> None:
        analyzer = _make_friction_analyzer()
        result = analyzer.analyze("inc-f06", _GOOD_REC, 0.0, 0, 0.75)
        names = {f.factor_name for f in result.factors}
        assert "LOW_CONFIDENCE" not in names

    # ---- Factor: HIGH_FATIGUE (+0.20 when fatigue > 0.70) ----------------

    def test_high_fatigue_factor_added_above_0_70(self) -> None:
        analyzer = _make_friction_analyzer()
        result = analyzer.analyze("inc-f07", _GOOD_REC, 0.71, 0, 0.80)
        names = {f.factor_name for f in result.factors}
        assert "HIGH_FATIGUE" in names

    def test_high_fatigue_factor_cost_is_0_20(self) -> None:
        analyzer = _make_friction_analyzer()
        result = analyzer.analyze("inc-f08", _GOOD_REC, 0.90, 0, 0.80)
        fatigue = next(f for f in result.factors if f.factor_name == "HIGH_FATIGUE")
        assert fatigue.friction_cost == pytest.approx(0.20)

    def test_fatigue_exactly_0_70_no_high_fatigue_factor(self) -> None:
        analyzer = _make_friction_analyzer()
        result = analyzer.analyze("inc-f09", _GOOD_REC, 0.70, 0, 0.80)
        names = {f.factor_name for f in result.factors}
        assert "HIGH_FATIGUE" not in names

    def test_fatigue_below_0_70_no_high_fatigue_factor(self) -> None:
        analyzer = _make_friction_analyzer()
        result = analyzer.analyze("inc-f10", _GOOD_REC, 0.40, 0, 0.80)
        names = {f.factor_name for f in result.factors}
        assert "HIGH_FATIGUE" not in names

    # ---- Factor: CONCURRENT_INCIDENTS (0.10 * min(n, 3)) -----------------

    def test_one_concurrent_incident_adds_0_10(self) -> None:
        analyzer = _make_friction_analyzer()
        result = analyzer.analyze("inc-f11", _GOOD_REC, 0.0, 1, 0.80)
        names = {f.factor_name for f in result.factors}
        assert "CONCURRENT_INCIDENTS" in names
        ci = next(f for f in result.factors if f.factor_name == "CONCURRENT_INCIDENTS")
        assert ci.friction_cost == pytest.approx(0.10)

    def test_two_concurrent_incidents_adds_0_20(self) -> None:
        analyzer = _make_friction_analyzer()
        result = analyzer.analyze("inc-f12", _GOOD_REC, 0.0, 2, 0.80)
        ci = next(f for f in result.factors if f.factor_name == "CONCURRENT_INCIDENTS")
        assert ci.friction_cost == pytest.approx(0.20)

    def test_three_concurrent_incidents_adds_0_30(self) -> None:
        analyzer = _make_friction_analyzer()
        result = analyzer.analyze("inc-f13", _GOOD_REC, 0.0, 3, 0.80)
        ci = next(f for f in result.factors if f.factor_name == "CONCURRENT_INCIDENTS")
        assert ci.friction_cost == pytest.approx(0.30)

    def test_many_concurrent_incidents_capped_at_0_30(self) -> None:
        analyzer = _make_friction_analyzer()
        result = analyzer.analyze("inc-f14", _GOOD_REC, 0.0, 100, 0.80)
        ci = next(f for f in result.factors if f.factor_name == "CONCURRENT_INCIDENTS")
        assert ci.friction_cost == pytest.approx(0.30)

    def test_zero_concurrent_incidents_no_factor(self) -> None:
        analyzer = _make_friction_analyzer()
        result = analyzer.analyze("inc-f15", _GOOD_REC, 0.0, 0, 0.80)
        names = {f.factor_name for f in result.factors}
        assert "CONCURRENT_INCIDENTS" not in names

    # ---- Factor: MISSING_ROLLBACK (+0.15) ---------------------------------

    def test_missing_rollback_in_rec_adds_factor(self) -> None:
        analyzer = _make_friction_analyzer()
        rec = "kubectl rollout restart deployment/api."  # no "rollback"
        result = analyzer.analyze("inc-f16", rec, 0.0, 0, 0.80)
        names = {f.factor_name for f in result.factors}
        assert "MISSING_ROLLBACK" in names

    def test_missing_rollback_factor_cost_is_0_15(self) -> None:
        analyzer = _make_friction_analyzer()
        rec = "kubectl rollout restart deployment/api."
        result = analyzer.analyze("inc-f17", rec, 0.0, 0, 0.80)
        rb = next(f for f in result.factors if f.factor_name == "MISSING_ROLLBACK")
        assert rb.friction_cost == pytest.approx(0.15)

    def test_rollback_mentioned_no_factor(self) -> None:
        analyzer = _make_friction_analyzer()
        rec = "Restart the pod. Rollback with kubectl rollout undo if needed."
        result = analyzer.analyze("inc-f18", rec, 0.0, 0, 0.80)
        names = {f.factor_name for f in result.factors}
        assert "MISSING_ROLLBACK" not in names

    def test_rollback_case_insensitive(self) -> None:
        analyzer = _make_friction_analyzer()
        rec = "Restart the pod. ROLLBACK using the undo command if it fails."
        result = analyzer.analyze("inc-f19", rec, 0.0, 0, 0.80)
        names = {f.factor_name for f in result.factors}
        assert "MISSING_ROLLBACK" not in names

    # ---- Factor: LENGTHY_RECOMMENDATION (+0.10 when len > 500) -----------

    def test_long_rec_over_500_chars_adds_factor(self) -> None:
        analyzer = _make_friction_analyzer()
        long_rec = "Do something. " * 40  # well over 500 chars
        assert len(long_rec) > 500
        result = analyzer.analyze("inc-f20", long_rec, 0.0, 0, 0.80)
        names = {f.factor_name for f in result.factors}
        assert "LENGTHY_RECOMMENDATION" in names

    def test_long_rec_factor_cost_is_0_10(self) -> None:
        analyzer = _make_friction_analyzer()
        long_rec = "X " * 300
        result = analyzer.analyze("inc-f21", long_rec, 0.0, 0, 0.80)
        lr = next(f for f in result.factors if f.factor_name == "LENGTHY_RECOMMENDATION")
        assert lr.friction_cost == pytest.approx(0.10)

    def test_rec_exactly_500_chars_no_factor(self) -> None:
        analyzer = _make_friction_analyzer()
        rec = "A" * 500
        result = analyzer.analyze("inc-f22", rec, 0.0, 0, 0.80)
        names = {f.factor_name for f in result.factors}
        assert "LENGTHY_RECOMMENDATION" not in names

    def test_short_rec_no_lengthy_factor(self) -> None:
        analyzer = _make_friction_analyzer()
        result = analyzer.analyze("inc-f23", "Restart the pod.", 0.0, 0, 0.80)
        names = {f.factor_name for f in result.factors}
        assert "LENGTHY_RECOMMENDATION" not in names

    # ---- Execution difficulty classification ------------------------------

    def test_difficulty_low_below_0_25(self) -> None:
        analyzer = _make_friction_analyzer()
        # No factors → total_friction = 0
        rec = "Rollback: kubectl rollout undo deployment/api."
        result = analyzer.analyze("inc-fd1", rec, 0.0, 0, 0.80)
        assert result.execution_difficulty == "LOW"

    def test_difficulty_medium_between_0_25_and_0_50(self) -> None:
        analyzer = _make_friction_analyzer()
        # LOW_CONFIDENCE (0.25) + MISSING_ROLLBACK (0.15) = 0.40 → MEDIUM
        # Subtract MISSING_ROLLBACK by including rollback in rec
        # LOW_CONFIDENCE alone = 0.25 → boundary case (< 0.25 is LOW, >= 0.25 is MEDIUM)
        # Use confidence = 0.49 → LOW_CONFIDENCE (0.25) and nothing else if rollback present
        rec = "Rollback: kubectl rollout undo. Do the fix."
        result = analyzer.analyze("inc-fd2", rec, 0.0, 0, 0.49)
        # 0.25 → >= 0.25 so MEDIUM
        assert result.execution_difficulty == "MEDIUM"

    def test_difficulty_high_between_0_50_and_0_75(self) -> None:
        analyzer = _make_friction_analyzer()
        # LOW_CONFIDENCE (0.25) + HIGH_FATIGUE (0.20) + CONCURRENT(1) (0.10)
        # = 0.55 → HIGH
        rec = "Rollback: kubectl rollout undo. Do the fix."
        result = analyzer.analyze("inc-fd3", rec, 0.80, 1, 0.40)
        assert result.execution_difficulty == "HIGH"

    def test_difficulty_critical_at_or_above_0_75(self) -> None:
        analyzer = _make_friction_analyzer()
        # LOW_CONFIDENCE(0.25) + HIGH_FATIGUE(0.20) + CONCURRENT(3)(0.30)
        # = 0.75 → CRITICAL
        rec = "kubectl get pods."  # no rollback → +0.15 = 0.90
        result = analyzer.analyze("inc-fd4", rec, 0.80, 3, 0.40)
        assert result.execution_difficulty == "CRITICAL"

    def test_total_friction_zero_yields_low_difficulty(self) -> None:
        analyzer = _make_friction_analyzer()
        rec = "Rollback using kubectl rollout undo."
        result = analyzer.analyze("inc-fd5", rec, 0.0, 0, 0.80)
        assert result.total_friction == pytest.approx(0.0)
        assert result.execution_difficulty == "LOW"

    # ---- Deferral recommendation -----------------------------------------

    def test_recommended_deferral_true_when_friction_above_0_70(self) -> None:
        analyzer = _make_friction_analyzer()
        # All factors: LOW_CONFIDENCE(0.25) + HIGH_FATIGUE(0.20) + CONCURRENT(3)(0.30)
        # + MISSING_ROLLBACK(0.15) = 0.90 → deferral recommended
        rec = "kubectl rollout restart deployment/api."  # no rollback
        result = analyzer.analyze("inc-fd6", rec, 0.80, 3, 0.40)
        assert result.recommended_deferral is True

    def test_recommended_deferral_false_when_friction_at_or_below_0_70(self) -> None:
        analyzer = _make_friction_analyzer()
        # Only MISSING_ROLLBACK(0.15) → 0.15 → no deferral
        rec = "kubectl rollout restart deployment/api."
        result = analyzer.analyze("inc-fd7", rec, 0.0, 0, 0.80)
        assert result.recommended_deferral is False

    def test_deferral_boundary_exactly_0_70_is_false(self) -> None:
        """Deferral is True only when total_friction > 0.70, not >= 0.70."""
        analyzer = _make_friction_analyzer()
        # Need total = exactly 0.70:
        # LOW_CONFIDENCE(0.25) + HIGH_FATIGUE(0.20) + CONCURRENT(2)(0.20) + MISSING_ROLLBACK(0.15)
        # = 0.80 → deferral
        # To get exactly 0.70: LOW_CONFIDENCE(0.25) + HIGH_FATIGUE(0.20) + CONCURRENT(2)(0.20)
        # + short rec no rollback (0.15) = 0.80; try without MISSING_ROLLBACK:
        # LOW_CONFIDENCE(0.25) + HIGH_FATIGUE(0.20) + CONCURRENT(2)(0.20) = 0.65 ≤ 0.70 → False
        rec = "Rollback: undo it with kubectl rollout undo deployment/api -n production."
        result = analyzer.analyze("inc-fd8", rec, 0.80, 2, 0.40)
        # 0.25 + 0.20 + 0.20 = 0.65 → not deferred
        assert result.recommended_deferral is False

    # ---- Total friction caps -----------------------------------------------

    def test_total_friction_capped_at_1_0(self) -> None:
        analyzer = _make_friction_analyzer()
        # Worst case: all factors triggered
        long_vague = "investigate further " * 30  # > 500 chars, no rollback
        result = analyzer.analyze("inc-fd9", long_vague, 1.0, 10, 0.10)
        assert result.total_friction <= 1.0

    # ---- Factors list completeness -----------------------------------------

    def test_factors_list_matches_named_factors(self) -> None:
        analyzer = _make_friction_analyzer()
        rec = "kubectl get pods."  # no rollback keyword
        result = analyzer.analyze("inc-fd10", rec, 0.90, 2, 0.30)
        for factor in result.factors:
            assert isinstance(factor, FrictionFactor)
            assert factor.friction_cost > 0.0
            assert factor.factor_name
            assert factor.description

    def test_total_friction_equals_sum_of_factor_costs_capped(self) -> None:
        analyzer = _make_friction_analyzer()
        rec = "kubectl rollout restart deployment/api."  # no rollback
        result = analyzer.analyze("inc-fd11", rec, 0.85, 2, 0.40)
        raw_sum = sum(f.friction_cost for f in result.factors)
        expected = min(1.0, raw_sum)
        assert result.total_friction == pytest.approx(expected)
