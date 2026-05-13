"""
Replay integration for SentinelOps Phase 47.

Bridges the Phase 47 live replay / ingestion / longitudinal systems with
the existing evaluation orchestration runner. Converts AgentPipelineOutputs
into EvaluationRecords for longitudinal tracking, and builds ReplaySessions
from pipeline execution traces.

Design:
  - Additive only — does NOT modify orchestration_runner.py
  - All functions are pure adapters with no side effects
  - Relies on golden labels from BenchmarkIncident (evaluation context only)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from evaluation.live.live_dataset_builder import EvaluationSample, LiveDatasetBuilder
from evaluation.live.longitudinal_metrics import EvaluationRecord
from runtime.continuous_evaluator import ContinuousEvaluator
from runtime.drift_monitor import DriftMonitor
from runtime.operational_regression import MetricSnapshot, OperationalRegressionDetector


@dataclass
class PipelineEvalRecord:
    """Adapter: AgentPipelineOutputs → EvaluationRecord."""

    benchmark_id: str
    execution_id: str
    correct: bool
    rootcause_confidence: float
    router_confidence: float
    severity: str
    telemetry_completeness: float
    timestamp_iso: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_evaluation_record(self) -> EvaluationRecord:
        return EvaluationRecord(
            sample_id=f"{self.benchmark_id}_{self.execution_id[:8]}",
            correct=self.correct,
            confidence=self.rootcause_confidence,
            severity=self.severity,
            telemetry_completeness=self.telemetry_completeness,
            timestamp_iso=self.timestamp_iso,
        )


def pipeline_outputs_to_eval_record(
    pipeline_outputs: Any,
    golden_root_cause: str,
    benchmark_severity: str = "error",
    telemetry_completeness: float = 1.0,
) -> PipelineEvalRecord:
    """
    Convert AgentPipelineOutputs to a PipelineEvalRecord.

    Correctness is determined by whether the top hypothesis mechanism
    matches the golden root cause (case-insensitive substring match).
    """
    rootcause_output = getattr(pipeline_outputs, "rootcause_output", None)
    router_output = getattr(pipeline_outputs, "router_output", None)

    top_mechanism = ""
    rootcause_conf = 0.0
    if rootcause_output and getattr(rootcause_output, "hypotheses", None):
        top_hyp = rootcause_output.hypotheses[0]
        top_mechanism = getattr(top_hyp, "mechanism", "") or ""
        rootcause_conf = float(getattr(top_hyp, "confidence", 0.0) or 0.0)

    router_conf = float(getattr(router_output, "confidence", 0.0) or 0.0) if router_output else 0.0

    correct = bool(
        golden_root_cause and top_mechanism and golden_root_cause.lower() in top_mechanism.lower()
    )

    return PipelineEvalRecord(
        benchmark_id=pipeline_outputs.benchmark_id,
        execution_id=pipeline_outputs.execution_id,
        correct=correct,
        rootcause_confidence=rootcause_conf,
        router_confidence=router_conf,
        severity=benchmark_severity,
        telemetry_completeness=telemetry_completeness,
    )


def pipeline_outputs_to_dataset_sample(
    pipeline_outputs: Any,
    golden_root_cause: str,
    golden_resolution: str,
    incident_events: list[dict[str, Any]] | None = None,
) -> EvaluationSample:
    """Build an EvaluationSample from pipeline outputs for dataset construction."""
    events = incident_events or []
    builder = LiveDatasetBuilder(dataset_id="pipeline_eval", version="1.0")
    sample = builder.ingest_replay_incident(
        incident_id=pipeline_outputs.benchmark_id,
        events=events,
        ground_truth_root_cause=golden_root_cause,
        ground_truth_resolution=golden_resolution,
    )
    return sample


class ReplayEvaluationBridge:
    """
    Connects the evaluation orchestration runner to Phase 47 runtime systems.

    Usage:
        bridge = ReplayEvaluationBridge()
        for outputs, benchmark in pipeline_results:
            bridge.ingest_pipeline_result(outputs, benchmark.golden_root_cause)
        report = bridge.evaluator.latest_report()
        drift_signals = bridge.drift_monitor.all_signals()
    """

    def __init__(
        self,
        window_size: int = 20,
        cycle_batch_size: int = 5,
    ) -> None:
        self.evaluator = ContinuousEvaluator(
            window_size=window_size,
            cycle_batch_size=cycle_batch_size,
        )
        self.drift_monitor = DriftMonitor(short_window=5, baseline_window=20)
        self.regression_detector = OperationalRegressionDetector()
        self._eval_records: list[PipelineEvalRecord] = []

    def ingest_pipeline_result(
        self,
        pipeline_outputs: Any,
        golden_root_cause: str,
        benchmark_severity: str = "error",
        telemetry_completeness: float = 1.0,
    ) -> PipelineEvalRecord:
        """Ingest one pipeline run result into the continuous evaluator."""
        record = pipeline_outputs_to_eval_record(
            pipeline_outputs,
            golden_root_cause=golden_root_cause,
            benchmark_severity=benchmark_severity,
            telemetry_completeness=telemetry_completeness,
        )
        self._eval_records.append(record)
        self.evaluator.ingest(record.to_evaluation_record())
        self.drift_monitor.observe(
            accuracy=1.0 if record.correct else 0.0,
            confidence=record.rootcause_confidence,
        )
        return record

    def run_cycles(self) -> None:
        """Drain pending evaluation records into cycles."""
        self.evaluator.run_all()

    def snapshot(self, run_id: str) -> MetricSnapshot | None:
        """Build a MetricSnapshot from the latest longitudinal report."""
        report = self.evaluator.latest_report()
        if report is None:
            return None
        windows = report.windows
        sev_weighted = (
            sum(w.severity_weighted_accuracy for w in windows) / len(windows) if windows else 0.0
        )
        comp_weighted = (
            sum(w.completeness_weighted_accuracy for w in windows) / len(windows)
            if windows
            else 0.0
        )
        return MetricSnapshot(
            run_id=run_id,
            accuracy=report.overall_accuracy,
            calibration_error=report.overall_calibration_error,
            severity_weighted_accuracy=sev_weighted,
            completeness_weighted_accuracy=comp_weighted,
            trend=report.trend,
            window_count=report.num_windows,
        )

    def compare_to_baseline(self, baseline: MetricSnapshot, candidate_run_id: str) -> Any:
        """Compare current snapshot to a saved baseline."""
        current = self.snapshot(candidate_run_id)
        if current is None:
            return None
        return self.regression_detector.compare(baseline, current)

    def total_ingested(self) -> int:
        return len(self._eval_records)

    def correct_rate(self) -> float:
        if not self._eval_records:
            return 0.0
        return sum(1 for r in self._eval_records if r.correct) / len(self._eval_records)
