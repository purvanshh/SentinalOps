"""Tests for evaluation replay integration (Phase 47 Commit 6)."""

from __future__ import annotations

from dataclasses import dataclass, field

from evaluation.live.longitudinal_metrics import EvaluationRecord
from evaluation.replay_integration import (
    ReplayEvaluationBridge,
    pipeline_outputs_to_eval_record,
)
from runtime.operational_regression import MetricSnapshot

# ---------------------------------------------------------------------------
# Minimal stubs to simulate AgentPipelineOutputs
# ---------------------------------------------------------------------------


@dataclass
class _Hypothesis:
    mechanism: str
    confidence: float


@dataclass
class _RootCauseOutput:
    hypotheses: list[_Hypothesis]


@dataclass
class _RouterOutput:
    confidence: float = 0.80


@dataclass
class _FakePipelineOutputs:
    benchmark_id: str = "BM-001"
    execution_id: str = "exec-abc123"
    rootcause_output: _RootCauseOutput = field(
        default_factory=lambda: _RootCauseOutput(
            hypotheses=[_Hypothesis(mechanism="db_connection_pool_exhaustion", confidence=0.82)]
        )
    )
    router_output: _RouterOutput = field(default_factory=_RouterOutput)


# ---------------------------------------------------------------------------
# pipeline_outputs_to_eval_record
# ---------------------------------------------------------------------------


class TestPipelineOutputsToEvalRecord:
    def test_correct_when_mechanism_matches(self):
        outputs = _FakePipelineOutputs()
        record = pipeline_outputs_to_eval_record(
            outputs, golden_root_cause="db_connection_pool_exhaustion"
        )
        assert record.correct is True

    def test_incorrect_when_mechanism_mismatch(self):
        outputs = _FakePipelineOutputs()
        record = pipeline_outputs_to_eval_record(outputs, golden_root_cause="memory_leak")
        assert record.correct is False

    def test_partial_match_correct(self):
        outputs = _FakePipelineOutputs()
        record = pipeline_outputs_to_eval_record(outputs, golden_root_cause="db_connection")
        assert record.correct is True

    def test_rootcause_confidence_extracted(self):
        outputs = _FakePipelineOutputs()
        record = pipeline_outputs_to_eval_record(outputs, golden_root_cause="")
        assert abs(record.rootcause_confidence - 0.82) < 0.01

    def test_router_confidence_extracted(self):
        outputs = _FakePipelineOutputs()
        record = pipeline_outputs_to_eval_record(outputs, golden_root_cause="")
        assert abs(record.router_confidence - 0.80) < 0.01

    def test_severity_passed_through(self):
        outputs = _FakePipelineOutputs()
        record = pipeline_outputs_to_eval_record(
            outputs, golden_root_cause="", benchmark_severity="critical"
        )
        assert record.severity == "critical"

    def test_empty_hypotheses_not_correct(self):
        outputs = _FakePipelineOutputs(rootcause_output=_RootCauseOutput(hypotheses=[]))
        record = pipeline_outputs_to_eval_record(outputs, golden_root_cause="anything")
        assert record.correct is False

    def test_to_evaluation_record_produces_correct_type(self):
        outputs = _FakePipelineOutputs()
        record = pipeline_outputs_to_eval_record(outputs, golden_root_cause="db_connection")
        ev = record.to_evaluation_record()
        assert isinstance(ev, EvaluationRecord)
        assert ev.correct is True

    def test_sample_id_format(self):
        outputs = _FakePipelineOutputs(benchmark_id="BM-42", execution_id="abcdef1234")
        record = pipeline_outputs_to_eval_record(outputs, golden_root_cause="")
        ev = record.to_evaluation_record()
        assert "BM-42" in ev.sample_id


# ---------------------------------------------------------------------------
# ReplayEvaluationBridge
# ---------------------------------------------------------------------------


class TestReplayEvaluationBridge:
    def _outputs(self, mechanism: str = "db_connection_pool_exhaustion") -> _FakePipelineOutputs:
        return _FakePipelineOutputs(
            rootcause_output=_RootCauseOutput(
                hypotheses=[_Hypothesis(mechanism=mechanism, confidence=0.80)]
            )
        )

    def test_ingest_and_total_count(self):
        bridge = ReplayEvaluationBridge()
        bridge.ingest_pipeline_result(self._outputs(), "db_connection_pool_exhaustion")
        assert bridge.total_ingested() == 1

    def test_correct_rate_all_correct(self):
        bridge = ReplayEvaluationBridge()
        for _ in range(5):
            bridge.ingest_pipeline_result(self._outputs(), "db_connection_pool_exhaustion")
        assert abs(bridge.correct_rate() - 1.0) < 0.01

    def test_correct_rate_all_wrong(self):
        bridge = ReplayEvaluationBridge()
        for _ in range(5):
            bridge.ingest_pipeline_result(self._outputs("wrong_mechanism"), "memory_leak")
        assert bridge.correct_rate() == 0.0

    def test_run_cycles_drains_pending(self):
        bridge = ReplayEvaluationBridge(cycle_batch_size=3)
        for _ in range(9):
            bridge.ingest_pipeline_result(self._outputs(), "db_connection_pool_exhaustion")
        bridge.run_cycles()
        assert bridge.evaluator.pending_count() == 0

    def test_latest_report_after_cycles(self):
        bridge = ReplayEvaluationBridge(cycle_batch_size=3, window_size=3)
        for _ in range(6):
            bridge.ingest_pipeline_result(self._outputs(), "db_connection_pool_exhaustion")
        bridge.run_cycles()
        assert bridge.evaluator.latest_report() is not None

    def test_snapshot_none_before_cycles(self):
        bridge = ReplayEvaluationBridge()
        assert bridge.snapshot("R1") is None

    def test_snapshot_after_cycles(self):
        bridge = ReplayEvaluationBridge(cycle_batch_size=3, window_size=3)
        for _ in range(6):
            bridge.ingest_pipeline_result(self._outputs(), "db_connection_pool_exhaustion")
        bridge.run_cycles()
        snapshot = bridge.snapshot("R1")
        assert snapshot is not None
        assert isinstance(snapshot, MetricSnapshot)
        assert snapshot.run_id == "R1"

    def test_drift_monitor_observed(self):
        bridge = ReplayEvaluationBridge()
        for _ in range(5):
            bridge.ingest_pipeline_result(self._outputs(), "db_connection_pool_exhaustion")
        # Just verify that the drift monitor received observations (buffer is not empty)
        assert len(bridge.drift_monitor._accuracy_buf) == 5

    def test_compare_to_baseline(self):
        bridge = ReplayEvaluationBridge(cycle_batch_size=3, window_size=3)
        for _ in range(6):
            bridge.ingest_pipeline_result(self._outputs(), "db_connection_pool_exhaustion")
        bridge.run_cycles()
        baseline = MetricSnapshot(
            run_id="baseline",
            accuracy=0.70,
            calibration_error=0.05,
            severity_weighted_accuracy=0.70,
            completeness_weighted_accuracy=0.70,
            trend="stable",
            window_count=3,
        )
        result = bridge.compare_to_baseline(baseline, "current")
        assert result is not None
        assert result.verdict in ("pass", "warn", "improvement")

    def test_compare_to_baseline_none_before_cycles(self):
        bridge = ReplayEvaluationBridge()
        baseline = MetricSnapshot(
            run_id="baseline",
            accuracy=0.70,
            calibration_error=0.05,
            severity_weighted_accuracy=0.70,
            completeness_weighted_accuracy=0.70,
            trend="stable",
            window_count=3,
        )
        result = bridge.compare_to_baseline(baseline, "current")
        assert result is None
