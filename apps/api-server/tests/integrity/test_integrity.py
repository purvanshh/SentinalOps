"""Tests for benchmark integrity enforcement."""

import pytest
from evaluation.integrity.anti_contamination import (
    AntiContaminationGuard,
    ContaminationError,
)
from evaluation.integrity.benchmark_invariants import (
    BenchmarkInvariantChecker,
    InvariantViolation,
)
from evaluation.integrity.evaluation_path_auditor import EvaluationPathAuditor


# ---------------------------------------------------------------------------
# AntiContaminationGuard
# ---------------------------------------------------------------------------

class TestAntiContaminationGuard:
    def _clean_sample(self) -> dict:
        return {
            "incident_id": "inc-001",
            "service": "payment-service",
            "severity": "high",
            "logs": ["ERROR: timeout"],
            "metrics": {"error_rate": 0.45},
        }

    def _contaminated_sample(self) -> dict:
        d = self._clean_sample()
        d["golden_label"] = "deployment_regression"
        return d

    def test_scrub_removes_contamination_field(self):
        guard = AntiContaminationGuard()
        scrubbed = guard.scrub(self._contaminated_sample())
        assert "golden_label" not in scrubbed
        assert "incident_id" in scrubbed

    def test_scrub_keeps_clean_fields(self):
        guard = AntiContaminationGuard()
        scrubbed = guard.scrub(self._clean_sample())
        assert scrubbed == self._clean_sample()

    def test_scrub_batch(self):
        guard = AntiContaminationGuard()
        samples = [self._contaminated_sample() for _ in range(5)]
        scrubbed = guard.scrub_batch(samples)
        assert all("golden_label" not in s for s in scrubbed)

    def test_check_clean_dataset(self):
        guard = AntiContaminationGuard()
        report = guard.check([self._clean_sample() for _ in range(10)])
        assert report.clean is True
        assert report.contamination_rate == 0.0
        assert report.severity == "none"

    def test_check_contaminated_dataset(self):
        guard = AntiContaminationGuard()
        samples = [self._contaminated_sample() for _ in range(10)]
        report = guard.check(samples)
        assert not report.clean
        assert "golden_label" in report.contaminated_fields
        assert report.contamination_rate == 1.0

    def test_check_partial_contamination(self):
        guard = AntiContaminationGuard()
        samples = [self._clean_sample() for _ in range(8)] + [self._contaminated_sample() for _ in range(2)]
        report = guard.check(samples)
        assert not report.clean
        assert report.contamination_rate == 0.2

    def test_assert_clean_passes_on_clean_data(self):
        guard = AntiContaminationGuard()
        guard.assert_clean([self._clean_sample()])  # must not raise

    def test_assert_clean_raises_on_contamination(self):
        guard = AntiContaminationGuard()
        with pytest.raises(ContaminationError):
            guard.assert_clean([self._contaminated_sample()])

    def test_root_cause_is_contamination_field(self):
        guard = AntiContaminationGuard()
        sample = self._clean_sample()
        sample["root_cause"] = "deployment_regression"
        report = guard.check([sample])
        assert not report.clean

    def test_true_label_is_contamination_field(self):
        guard = AntiContaminationGuard()
        sample = self._clean_sample()
        sample["true_label"] = "network_partition"
        report = guard.check([sample])
        assert not report.clean

    def test_severity_critical_when_pervasive(self):
        guard = AntiContaminationGuard()
        samples = [self._contaminated_sample() for _ in range(30)]
        report = guard.check(samples)
        assert report.severity == "critical"

    def test_report_serializable(self):
        import json
        guard = AntiContaminationGuard()
        report = guard.check([self._clean_sample()])
        json.dumps(report.to_dict())


# ---------------------------------------------------------------------------
# BenchmarkInvariantChecker
# ---------------------------------------------------------------------------

class TestBenchmarkInvariantChecker:
    def _clean_context(self) -> dict:
        return {
            "scorer_inputs": [{"incident_id": "inc-001", "severity": "high"}],
            "predictions": [{"confidence": 0.75, "attribution": "network"}],
            "evaluation_uses_mock_outputs": False,
            "evaluation_only_code_path_active": False,
        }

    def test_clean_context_all_pass(self):
        checker = BenchmarkInvariantChecker()
        result = checker.run_all(self._clean_context())
        assert result.all_passed is True
        assert result.violations == []

    def test_golden_label_in_scorer_input_violates(self):
        checker = BenchmarkInvariantChecker()
        ctx = self._clean_context()
        ctx["scorer_inputs"] = [{"incident_id": "inc-001", "golden_label": "network"}]
        result = checker.run_all(ctx)
        violated = [v.invariant_name for v in result.violations]
        assert "scorer_never_sees_labels" in violated

    def test_confidence_out_of_bounds_violates(self):
        checker = BenchmarkInvariantChecker()
        ctx = self._clean_context()
        ctx["predictions"] = [{"confidence": 1.5, "attribution": "network"}]
        result = checker.run_all(ctx)
        violated = [v.invariant_name for v in result.violations]
        assert "confidence_in_unit_interval" in violated

    def test_attribution_below_threshold_violates(self):
        checker = BenchmarkInvariantChecker()
        ctx = self._clean_context()
        ctx["predictions"] = [{"confidence": 0.10, "attribution": "network", "uncertainty_flagged": False}]
        result = checker.run_all(ctx)
        violated = [v.invariant_name for v in result.violations]
        assert "attribution_requires_minimum_confidence" in violated

    def test_mock_outputs_violates(self):
        checker = BenchmarkInvariantChecker()
        ctx = self._clean_context()
        ctx["evaluation_uses_mock_outputs"] = True
        result = checker.run_all(ctx)
        violated = [v.invariant_name for v in result.violations]
        assert "evaluation_uses_runtime_outputs" in violated

    def test_shortcut_path_violates(self):
        checker = BenchmarkInvariantChecker()
        ctx = self._clean_context()
        ctx["evaluation_only_code_path_active"] = True
        result = checker.run_all(ctx)
        violated = [v.invariant_name for v in result.violations]
        assert "no_evaluation_only_shortcuts" in violated

    def test_checks_run_count(self):
        checker = BenchmarkInvariantChecker()
        result = checker.run_all(self._clean_context())
        assert result.checks_run == 5

    def test_custom_check_registered(self):
        checker = BenchmarkInvariantChecker()

        def my_check(ctx: dict) -> InvariantViolation | None:
            if ctx.get("custom_flag"):
                return InvariantViolation("custom", "custom check failed", {})
            return None

        checker.register("custom_invariant", my_check)
        result = checker.run_all({**self._clean_context(), "custom_flag": True})
        assert any(v.invariant_name == "custom" for v in result.violations)

    def test_result_serializable(self):
        import json
        checker = BenchmarkInvariantChecker()
        result = checker.run_all(self._clean_context())
        json.dumps(result.to_dict())


# ---------------------------------------------------------------------------
# EvaluationPathAuditor
# ---------------------------------------------------------------------------

class TestEvaluationPathAuditor:
    def _clean_context(self) -> dict:
        return {
            "production_confidence_calibrator": True,
            "production_uncertainty_handler": True,
            "production_path_uses_golden_data": False,
            "evaluation_applies_extra_cleaning": False,
            "evaluation_uses_future_data": False,
            "evaluation_disables_uncertainty": False,
            "synthetic_dataset_only": False,
        }

    def test_clean_context_aligned(self):
        auditor = EvaluationPathAuditor()
        report = auditor.audit(self._clean_context())
        assert report.paths_aligned is True
        assert report.synthetic_inflation_risk == "none"

    def test_missing_calibrator_causes_divergence(self):
        auditor = EvaluationPathAuditor()
        ctx = self._clean_context()
        ctx["production_confidence_calibrator"] = False
        report = auditor.audit(ctx)
        assert not report.production_path_verified
        assert not report.paths_aligned

    def test_extra_cleaning_causes_divergence(self):
        auditor = EvaluationPathAuditor()
        ctx = self._clean_context()
        ctx["evaluation_applies_extra_cleaning"] = True
        report = auditor.audit(ctx)
        assert not report.evaluation_path_verified

    def test_future_data_causes_divergence(self):
        auditor = EvaluationPathAuditor()
        ctx = self._clean_context()
        ctx["evaluation_uses_future_data"] = True
        report = auditor.audit(ctx)
        assert "evaluation_uses_data_not_available_at_inference_time" in report.divergence_points

    def test_inflation_risk_high_when_many_issues(self):
        auditor = EvaluationPathAuditor()
        ctx = {
            "evaluation_applies_extra_cleaning": True,
            "evaluation_uses_future_data": True,
            "evaluation_disables_uncertainty": True,
            "synthetic_dataset_only": True,
        }
        report = auditor.audit(ctx)
        assert report.synthetic_inflation_risk in ("medium", "high")

    def test_report_serializable(self):
        import json
        auditor = EvaluationPathAuditor()
        report = auditor.audit(self._clean_context())
        json.dumps(report.to_dict())
