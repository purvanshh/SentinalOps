"""Tests for adversarial red-team evaluation framework."""

from evaluation.redteam.adversarial_scenarios import (
    AdversarialScenario,
    AttackType,
    ScenarioLibrary,
)
from evaluation.redteam.realism_scores import AdversarialRealismScorer
from evaluation.redteam.redteam_evaluator import RedTeamEvaluator, RedTeamResult

# ---------------------------------------------------------------------------
# Scenario library
# ---------------------------------------------------------------------------


class TestScenarioLibrary:
    def test_all_scenarios_returns_nine(self):
        scenarios = ScenarioLibrary.all_scenarios()
        assert len(scenarios) == 9

    def test_all_scenarios_have_unique_ids(self):
        scenarios = ScenarioLibrary.all_scenarios()
        ids = [s.scenario_id for s in scenarios]
        assert len(ids) == len(set(ids))

    def test_all_attack_types_covered(self):
        scenarios = ScenarioLibrary.all_scenarios()
        types = {s.attack_type for s in scenarios}
        assert AttackType.PROMPT_INJECTION in types
        assert AttackType.FAKE_TELEMETRY in types
        assert AttackType.CAUSAL_SPOOFING in types
        assert AttackType.ESCALATION_SPAM in types

    def test_by_type_filters_correctly(self):
        injection_scenarios = ScenarioLibrary.by_type(AttackType.PROMPT_INJECTION)
        assert all(s.attack_type == AttackType.PROMPT_INJECTION for s in injection_scenarios)

    def test_each_scenario_has_payload(self):
        for s in ScenarioLibrary.all_scenarios():
            assert isinstance(s.incident_payload, dict)
            assert "incident_id" in s.incident_payload

    def test_to_dict_serializable(self):
        import json

        for s in ScenarioLibrary.all_scenarios():
            d = s.to_dict()
            json.dumps(d)  # must not raise


# ---------------------------------------------------------------------------
# RedTeamEvaluator
# ---------------------------------------------------------------------------


class TestRedTeamEvaluator:
    def _honest_response(self, scenario: AdversarialScenario) -> dict:
        """Simulate an honest system response that should pass most checks."""
        return {
            "confidence": 0.35,
            "attribution": None,
            "uncertainty_flagged": True,
            "refused": False,
            "explanation": "Insufficient evidence to attribute with confidence.",
        }

    def _dishonest_response(self, scenario: AdversarialScenario) -> dict:
        """Simulate an overconfident / injection-inflated response."""
        return {
            "confidence": 0.99,
            "attribution": "deployment_regression",
            "uncertainty_flagged": False,
            "refused": False,
            "explanation": "Confident attribution.",
        }

    def test_honest_response_passes_prompt_injection(self):
        evaluator = RedTeamEvaluator()
        scenario = ScenarioLibrary.by_type(AttackType.PROMPT_INJECTION)[0]
        response = self._honest_response(scenario)
        result = evaluator.evaluate_scenario(scenario, response)
        assert result.passed

    def test_inflated_response_fails_prompt_injection(self):
        evaluator = RedTeamEvaluator()
        scenario = ScenarioLibrary.by_type(AttackType.PROMPT_INJECTION)[0]
        response = self._dishonest_response(scenario)
        result = evaluator.evaluate_scenario(scenario, response)
        assert not result.passed

    def test_confidence_collapse_detected(self):
        evaluator = RedTeamEvaluator()
        scenario = ScenarioLibrary.by_type(AttackType.FAKE_TELEMETRY)[0]
        # Low confidence → collapse detected → should pass
        response = {"confidence": 0.15, "telemetry_corrupted": True, "uncertainty_flagged": True}
        result = evaluator.evaluate_scenario(scenario, response)
        assert result.confidence_collapsed_correctly is True

    def test_confidence_collapse_missing_fails(self):
        evaluator = RedTeamEvaluator()
        scenario = ScenarioLibrary.by_type(AttackType.FAKE_TELEMETRY)[0]
        # High confidence despite corrupted telemetry → should fail
        response = {"confidence": 0.95, "telemetry_corrupted": False, "uncertainty_flagged": False}
        result = evaluator.evaluate_scenario(scenario, response)
        assert not result.confidence_collapsed_correctly

    def test_causal_spoofing_refusal(self):
        evaluator = RedTeamEvaluator()
        scenario = ScenarioLibrary.by_type(AttackType.CAUSAL_SPOOFING)[0]
        # Low confidence + no attribution = refusal
        response = {"confidence": 0.10, "attribution": None, "refused": True}
        result = evaluator.evaluate_scenario(scenario, response)
        assert result.refusal_correct is True

    def test_result_to_dict(self):
        import json

        evaluator = RedTeamEvaluator()
        scenario = ScenarioLibrary.all_scenarios()[0]
        result = evaluator.evaluate_scenario(scenario, self._honest_response(scenario))
        json.dumps(result.to_dict())  # must not raise

    def test_full_suite_structure(self):
        evaluator = RedTeamEvaluator()
        output = evaluator.run_full_suite(self._honest_response)
        assert "total_scenarios" in output
        assert "pass_rate" in output
        assert output["total_scenarios"] == 9
        assert 0.0 <= output["pass_rate"] <= 1.0

    def test_full_suite_dishonest_fails_many(self):
        evaluator = RedTeamEvaluator()
        output = evaluator.run_full_suite(self._dishonest_response)
        assert output["pass_rate"] < 0.60

    def test_overall_assessment_present(self):
        evaluator = RedTeamEvaluator()
        output = evaluator.run_full_suite(self._honest_response)
        assert "overall_assessment" in output


# ---------------------------------------------------------------------------
# AdversarialRealismScorer
# ---------------------------------------------------------------------------


class TestAdversarialRealismScorer:
    def _make_results(self, passed: bool) -> list[RedTeamResult]:
        return [
            RedTeamResult(
                scenario_id=s.scenario_id,
                attack_type=s.attack_type.value,
                passed=passed,
                confidence_collapsed_correctly=passed,
                refusal_correct=passed,
                observed_confidence=0.35 if passed else 0.95,
                notes="",
            )
            for s in ScenarioLibrary.all_scenarios()
        ]

    def test_all_pass_produces_high_score(self):
        scorer = AdversarialRealismScorer()
        report = scorer.score(self._make_results(passed=True))
        assert report.composite_score >= 0.90
        assert report.grade == "A"

    def test_all_fail_produces_low_score(self):
        scorer = AdversarialRealismScorer()
        report = scorer.score(self._make_results(passed=False))
        assert report.composite_score < 0.50

    def test_report_has_all_dimensions(self):
        scorer = AdversarialRealismScorer()
        report = scorer.score(self._make_results(passed=True))
        assert 0.0 <= report.attribution_resilience <= 1.0
        assert 0.0 <= report.deception_resistance <= 1.0
        assert 0.0 <= report.telemetry_spoof_resistance <= 1.0
        assert 0.0 <= report.escalation_integrity <= 1.0
        assert 0.0 <= report.hallucination_resistance <= 1.0

    def test_to_dict_serializable(self):
        import json

        scorer = AdversarialRealismScorer()
        report = scorer.score(self._make_results(passed=True))
        json.dumps(report.to_dict())

    def test_score_from_suite(self):
        evaluator = RedTeamEvaluator()
        scorer = AdversarialRealismScorer()

        def honest(s):
            return {
                "confidence": 0.30,
                "attribution": None,
                "uncertainty_flagged": True,
                "refused": True,
            }

        suite_output = evaluator.run_full_suite(honest)
        report = scorer.score_from_suite(suite_output)
        assert isinstance(report.composite_score, float)

    def test_grade_mapping(self):
        scorer = AdversarialRealismScorer()
        assert scorer._grade(0.95) == "A"
        assert scorer._grade(0.82) == "B"
        assert scorer._grade(0.71) == "C"
        assert scorer._grade(0.61) == "D"
        assert scorer._grade(0.40) == "F"
