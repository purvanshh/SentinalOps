"""
Regression evaluation framework tests.

Validates:
- Benchmark replay produces deterministic results
- Replay hash is stable
- Regression detection correctly identifies degradation
- Improvement detection works
- No false regression on identical runs
"""

import pytest
from evaluation.benchmark_suite import load_benchmark_suite
from evaluation.regression.benchmark_replay import ReplayResult, replay_benchmark
from evaluation.regression.regression_evaluator import (
    compare_runs,
    detect_regressions,
)


@pytest.fixture(scope="module")
def suite():
    return load_benchmark_suite()


@pytest.fixture(scope="module")
def baseline_result(suite) -> ReplayResult:
    return replay_benchmark(suite)


class TestBenchmarkReplay:
    def test_replay_produces_result(self, baseline_result: ReplayResult) -> None:
        assert baseline_result is not None

    def test_replay_has_correct_incident_count(self, suite, baseline_result: ReplayResult) -> None:
        assert baseline_result.total_incidents == len(suite.incidents)

    def test_replay_has_replay_hash(self, baseline_result: ReplayResult) -> None:
        assert baseline_result.replay_hash and len(baseline_result.replay_hash) == 16

    def test_replay_is_deterministic(self, suite) -> None:
        result1 = replay_benchmark(suite)
        result2 = replay_benchmark(suite)
        assert result1.replay_hash == result2.replay_hash, "Replay hash must be stable"
        assert result1.aggregate_trustworthiness_score == result2.aggregate_trustworthiness_score
        assert result1.aggregate_safety_score == result2.aggregate_safety_score

    def test_replay_has_router_quality(self, baseline_result: ReplayResult) -> None:
        assert "accuracy" in baseline_result.router_quality

    def test_replay_has_calibration(self, baseline_result: ReplayResult) -> None:
        assert "expected_calibration_error" in baseline_result.calibration

    def test_replay_has_remediation_quality(self, baseline_result: ReplayResult) -> None:
        assert "mean_quality_score" in baseline_result.remediation_quality

    def test_replay_has_execution_safety(self, baseline_result: ReplayResult) -> None:
        assert "mean_safety_score" in baseline_result.execution_safety

    def test_replay_has_operator_trust(self, baseline_result: ReplayResult) -> None:
        assert "trust_score" in baseline_result.operator_trust

    def test_replay_has_hallucination_summary(self, baseline_result: ReplayResult) -> None:
        assert "hallucination_detection_rate" in baseline_result.hallucination_summary

    def test_trustworthiness_score_in_range(self, baseline_result: ReplayResult) -> None:
        assert 0.0 <= baseline_result.aggregate_trustworthiness_score <= 1.0

    def test_safety_score_in_range(self, baseline_result: ReplayResult) -> None:
        assert 0.0 <= baseline_result.aggregate_safety_score <= 1.0

    def test_autonomous_readiness_in_range(self, baseline_result: ReplayResult) -> None:
        assert 0.0 <= baseline_result.aggregate_autonomous_readiness_score <= 1.0

    def test_to_dict_serializable(self, baseline_result: ReplayResult) -> None:
        import json

        json.dumps(baseline_result.to_dict())


class TestRegressionDetection:
    def test_identical_runs_have_no_regressions(self, suite) -> None:
        result = replay_benchmark(suite)
        regressions = detect_regressions(result, result)
        assert (
            len(regressions) == 0
        ), f"Identical runs should have no regressions, got: {[r.metric for r in regressions]}"

    def test_degraded_accuracy_detected_as_regression(self, baseline_result: ReplayResult) -> None:
        degraded = ReplayResult(
            suite_id=baseline_result.suite_id,
            suite_version=baseline_result.suite_version,
            replay_timestamp=baseline_result.replay_timestamp,
            total_incidents=baseline_result.total_incidents,
            replay_hash="degraded-hash-123456",
            router_quality={
                **baseline_result.router_quality,
                "accuracy": max(0.0, baseline_result.router_quality["accuracy"] - 0.10),
            },
            calibration=baseline_result.calibration,
            remediation_quality=baseline_result.remediation_quality,
            execution_safety=baseline_result.execution_safety,
            operator_trust=baseline_result.operator_trust,
            hallucination_summary=baseline_result.hallucination_summary,
            aggregate_trustworthiness_score=baseline_result.aggregate_trustworthiness_score - 0.08,
            aggregate_safety_score=baseline_result.aggregate_safety_score,
            aggregate_autonomous_readiness_score=(
                baseline_result.aggregate_autonomous_readiness_score - 0.08
            ),
        )
        regressions = detect_regressions(baseline_result, degraded)
        regression_metrics = [r.metric for r in regressions]
        assert "accuracy" in regression_metrics or "trustworthiness" in regression_metrics

    def test_improved_accuracy_detected_as_improvement(self, baseline_result: ReplayResult) -> None:
        improved = ReplayResult(
            suite_id=baseline_result.suite_id,
            suite_version=baseline_result.suite_version,
            replay_timestamp=baseline_result.replay_timestamp,
            total_incidents=baseline_result.total_incidents,
            replay_hash="improved-hash-123456",
            router_quality={
                **baseline_result.router_quality,
                "accuracy": min(1.0, baseline_result.router_quality["accuracy"] + 0.10),
            },
            calibration=baseline_result.calibration,
            remediation_quality=baseline_result.remediation_quality,
            execution_safety=baseline_result.execution_safety,
            operator_trust=baseline_result.operator_trust,
            hallucination_summary=baseline_result.hallucination_summary,
            aggregate_trustworthiness_score=baseline_result.aggregate_trustworthiness_score + 0.08,
            aggregate_safety_score=baseline_result.aggregate_safety_score,
            aggregate_autonomous_readiness_score=(
                baseline_result.aggregate_autonomous_readiness_score + 0.08
            ),
        )
        report = compare_runs(baseline_result, improved)
        assert len(report.improvements) > 0

    def test_regression_report_has_hashes(self, baseline_result: ReplayResult) -> None:
        report = compare_runs(baseline_result, baseline_result)
        assert report.baseline_hash == report.current_hash

    def test_regression_severity_levels_valid(self, baseline_result: ReplayResult) -> None:
        degraded = ReplayResult(
            suite_id=baseline_result.suite_id,
            suite_version=baseline_result.suite_version,
            replay_timestamp=baseline_result.replay_timestamp,
            total_incidents=baseline_result.total_incidents,
            replay_hash="severity-test-1234",
            router_quality={**baseline_result.router_quality, "accuracy": 0.0, "macro_f1": 0.0},
            calibration=baseline_result.calibration,
            remediation_quality=baseline_result.remediation_quality,
            execution_safety=baseline_result.execution_safety,
            operator_trust=baseline_result.operator_trust,
            hallucination_summary=baseline_result.hallucination_summary,
            aggregate_trustworthiness_score=0.0,
            aggregate_safety_score=0.0,
            aggregate_autonomous_readiness_score=0.0,
        )
        report = compare_runs(baseline_result, degraded)
        for r in report.regressions:
            assert r.severity in ("LOW", "MEDIUM", "HIGH", "CRITICAL")

    def test_to_dict_serializable(self, baseline_result: ReplayResult) -> None:
        import json

        report = compare_runs(baseline_result, baseline_result)
        json.dumps(report.to_dict())
