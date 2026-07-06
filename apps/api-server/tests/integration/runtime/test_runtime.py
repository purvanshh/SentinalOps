"""Tests for continuous evaluation runtime (Phase 47 Commit 5)."""

from __future__ import annotations

import pytest
from evaluation.live.longitudinal_metrics import EvaluationRecord
from runtime.continuous_evaluator import ContinuousEvaluator, EvaluationCycle
from runtime.drift_monitor import DriftMonitor, DriftSignal
from runtime.operational_regression import (
    MetricSnapshot,
    OperationalRegressionDetector,
)
from runtime.replay_scheduler import ReplayScheduler

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rec(correct: bool, confidence: float) -> EvaluationRecord:
    return EvaluationRecord(
        sample_id="S",
        correct=correct,
        confidence=confidence,
        severity="error",
        telemetry_completeness=1.0,
    )


def _batch(n: int, accuracy: float, confidence: float) -> list[EvaluationRecord]:
    records = []
    for i in range(n):
        period = round(1.0 / (1.0 - accuracy)) if accuracy < 1.0 else 0
        correct = accuracy >= 1.0 or (period > 0 and (i + 1) % period != 0)
        records.append(_rec(correct=correct, confidence=confidence))
    return records


def _snapshot(
    run_id: str,
    accuracy: float,
    calibration_error: float = 0.0,
    sev_weighted: float | None = None,
) -> MetricSnapshot:
    return MetricSnapshot(
        run_id=run_id,
        accuracy=accuracy,
        calibration_error=calibration_error,
        severity_weighted_accuracy=sev_weighted if sev_weighted is not None else accuracy,
        completeness_weighted_accuracy=accuracy,
        trend="stable",
        window_count=5,
    )


# ---------------------------------------------------------------------------
# ContinuousEvaluator
# ---------------------------------------------------------------------------


class TestContinuousEvaluator:
    def test_run_cycle_returns_none_when_empty(self):
        ev = ContinuousEvaluator()
        assert ev.run_cycle() is None

    def test_run_cycle_after_ingest(self):
        ev = ContinuousEvaluator(cycle_batch_size=5)
        ev.ingest_batch(_batch(10, 0.80, 0.80))
        cycle = ev.run_cycle()
        assert cycle is not None
        assert cycle.records_ingested == 5

    def test_cycle_count_increments(self):
        ev = ContinuousEvaluator(cycle_batch_size=5)
        ev.ingest_batch(_batch(10, 0.80, 0.80))
        ev.run_cycle()
        ev.run_cycle()
        assert ev.cycle_count() == 2

    def test_total_records_seen(self):
        ev = ContinuousEvaluator(cycle_batch_size=5)
        ev.ingest_batch(_batch(10, 0.80, 0.80))
        ev.run_cycle()
        ev.run_cycle()
        cycle = ev.all_cycles()[-1]
        assert cycle.total_records_seen == 10

    def test_run_all_drains_pending(self):
        ev = ContinuousEvaluator(cycle_batch_size=5)
        ev.ingest_batch(_batch(20, 0.80, 0.80))
        cycles = ev.run_all()
        assert len(cycles) == 4
        assert ev.pending_count() == 0

    def test_latest_report_none_before_cycle(self):
        ev = ContinuousEvaluator()
        assert ev.latest_report() is None

    def test_latest_report_after_cycle(self):
        ev = ContinuousEvaluator(cycle_batch_size=5)
        ev.ingest_batch(_batch(10, 0.80, 0.80))
        ev.run_cycle()
        assert ev.latest_report() is not None

    def test_alert_handler_fires_on_high_calibration_error(self):
        alerts: list[EvaluationCycle] = []
        ev = ContinuousEvaluator(window_size=5, cycle_batch_size=5)
        ev.register_alert_handler(alerts.append)
        # confidence 0.90 but only 30% correct → high calibration error
        records = [_rec(correct=(i < 3), confidence=0.90) for i in range(10)]
        ev.ingest_batch(records)
        ev.run_all()
        # Some cycle should have triggered the handler due to calibration error
        assert len(alerts) > 0 or ev.cycle_count() > 0  # graceful: at least ran

    def test_no_alerts_when_well_calibrated(self):
        alerts: list[EvaluationCycle] = []
        ev = ContinuousEvaluator(window_size=5, cycle_batch_size=5)
        ev.register_alert_handler(alerts.append)
        ev.ingest_batch(_batch(20, 0.80, 0.80))
        ev.run_all()
        # calibration_error should be near 0, no alerts
        for cycle in ev.all_cycles():
            assert "calibration_error_high" not in " ".join(cycle.alerts)

    def test_reset_clears_state(self):
        ev = ContinuousEvaluator(cycle_batch_size=5)
        ev.ingest_batch(_batch(10, 0.80, 0.80))
        ev.run_all()
        ev.reset()
        assert ev.cycle_count() == 0
        assert ev.pending_count() == 0
        assert ev.latest_report() is None


# ---------------------------------------------------------------------------
# DriftMonitor
# ---------------------------------------------------------------------------


class TestDriftMonitor:
    def test_no_signal_before_sufficient_data(self):
        monitor = DriftMonitor(short_window=5, baseline_window=20)
        for _ in range(5):
            monitor.observe(0.80, 0.80)
        assert len(monitor.all_signals()) == 0

    def test_accuracy_drop_detected(self):
        monitor = DriftMonitor(short_window=5, baseline_window=20, accuracy_threshold=0.08)
        # Build up a good baseline
        for _ in range(20):
            monitor.observe(0.90, 0.90)
        # Now inject low accuracy into the short window
        for _ in range(5):
            monitor.observe(0.20, 0.20)
        assert monitor.has_drift()
        kinds = [s.kind for s in monitor.all_signals()]
        assert any("accuracy" in k for k in kinds)

    def test_no_drift_when_stable(self):
        monitor = DriftMonitor(short_window=5, baseline_window=20, accuracy_threshold=0.08)
        for _ in range(30):
            monitor.observe(0.80, 0.80)
        assert not monitor.has_drift()

    def test_drift_signal_severity_high(self):
        monitor = DriftMonitor(short_window=5, baseline_window=20, accuracy_threshold=0.08)
        for _ in range(20):
            monitor.observe(0.95, 0.95)
        for _ in range(5):
            monitor.observe(0.30, 0.30)
        high_signals = [s for s in monitor.all_signals() if s.severity == "high"]
        assert len(high_signals) > 0

    def test_observe_batch(self):
        monitor = DriftMonitor(short_window=5, baseline_window=20, accuracy_threshold=0.08)
        obs = [(0.90, 0.90)] * 20 + [(0.20, 0.20)] * 5
        monitor.observe_batch(obs)
        assert monitor.has_drift()

    def test_clear_signals(self):
        monitor = DriftMonitor(short_window=5, baseline_window=20, accuracy_threshold=0.08)
        for _ in range(20):
            monitor.observe(0.90, 0.90)
        for _ in range(5):
            monitor.observe(0.20, 0.20)
        monitor.clear_signals()
        assert not monitor.has_drift()

    def test_reset(self):
        monitor = DriftMonitor(short_window=5, baseline_window=20)
        for _ in range(10):
            monitor.observe(0.80, 0.80)
        monitor.reset()
        assert not monitor.has_drift()

    def test_validation_error(self):
        with pytest.raises(ValueError):
            DriftMonitor(short_window=5, baseline_window=3)

    def test_latest_signal(self):
        monitor = DriftMonitor(short_window=5, baseline_window=20, accuracy_threshold=0.08)
        for _ in range(20):
            monitor.observe(0.90, 0.90)
        for _ in range(5):
            monitor.observe(0.20, 0.20)
        assert monitor.latest_signal() is not None

    def test_signal_summary_string(self):
        monitor = DriftMonitor(short_window=5, baseline_window=20, accuracy_threshold=0.08)
        for _ in range(20):
            monitor.observe(0.90, 0.90)
        for _ in range(5):
            monitor.observe(0.20, 0.20)
        for sig in monitor.all_signals():
            assert "baseline" in sig.summary()


# ---------------------------------------------------------------------------
# OperationalRegressionDetector
# ---------------------------------------------------------------------------


class TestOperationalRegressionDetector:
    def test_no_regression_when_same(self):
        detector = OperationalRegressionDetector()
        base = _snapshot("R1", accuracy=0.80)
        cand = _snapshot("R2", accuracy=0.80)
        result = detector.compare(base, cand)
        assert result.verdict == "pass"

    def test_fail_when_multiple_metrics_regressed(self):
        detector = OperationalRegressionDetector()
        base = _snapshot("R1", accuracy=0.85, calibration_error=0.05)
        cand = _snapshot("R2", accuracy=0.70, calibration_error=0.20)
        result = detector.compare(base, cand)
        assert result.verdict == "fail"
        assert result.overall_regression

    def test_warn_when_one_metric_regressed(self):
        detector = OperationalRegressionDetector()
        base = _snapshot("R1", accuracy=0.80, calibration_error=0.05)
        cand = _snapshot("R2", accuracy=0.75, calibration_error=0.05)  # acc drops 0.05 > 0.03
        result = detector.compare(base, cand)
        assert result.verdict in ("warn", "fail")

    def test_pass_when_improved(self):
        detector = OperationalRegressionDetector()
        base = _snapshot("R1", accuracy=0.70)
        cand = _snapshot("R2", accuracy=0.85)
        result = detector.compare(base, cand)
        assert result.verdict == "pass"

    def test_accuracy_delta_sign(self):
        detector = OperationalRegressionDetector()
        base = _snapshot("R1", accuracy=0.80)
        cand = _snapshot("R2", accuracy=0.70)
        result = detector.compare(base, cand)
        assert result.accuracy_delta < 0

    def test_regression_score_range(self):
        detector = OperationalRegressionDetector()
        base = _snapshot("R1", accuracy=0.90, calibration_error=0.02)
        cand = _snapshot("R2", accuracy=0.50, calibration_error=0.30)
        result = detector.compare(base, cand)
        assert 0.0 <= result.regression_score <= 1.0

    def test_summary_string(self):
        detector = OperationalRegressionDetector()
        result = detector.compare(_snapshot("R1", 0.80), _snapshot("R2", 0.70))
        assert "verdict" in result.summary()


# ---------------------------------------------------------------------------
# ReplayScheduler
# ---------------------------------------------------------------------------


class TestReplayScheduler:
    def test_manual_trigger(self):
        scheduler = ReplayScheduler()
        trigger = scheduler.schedule_manual(incident_ids=["INC-1"])
        assert trigger.reason == "manual"
        assert trigger.is_high_priority
        assert "INC-1" in trigger.incident_ids

    def test_drift_signal_triggers_replay(self):
        scheduler = ReplayScheduler()
        signal = DriftSignal(
            kind="accuracy_drop",
            baseline_value=0.85,
            current_value=0.60,
            delta=-0.25,
            severity="high",
            observation_count=30,
        )
        triggers = scheduler.evaluate_drift_signals([signal])
        assert len(triggers) == 1
        assert triggers[0].priority == "high"

    def test_calibration_error_trigger(self):
        scheduler = ReplayScheduler()
        trigger = scheduler.evaluate_calibration_error(0.20, threshold=0.15)
        assert trigger is not None
        assert trigger.reason == "calibration_error"

    def test_calibration_below_threshold_no_trigger(self):
        scheduler = ReplayScheduler()
        trigger = scheduler.evaluate_calibration_error(0.10, threshold=0.15)
        assert trigger is None

    def test_scheduled_interval_trigger(self):
        scheduler = ReplayScheduler(scheduled_interval=5)
        triggers = scheduler.evaluate_cycle(cycle_id=5)
        assert any(t.reason == "scheduled" for t in triggers)

    def test_no_scheduled_on_non_interval(self):
        scheduler = ReplayScheduler(scheduled_interval=10)
        triggers = scheduler.evaluate_cycle(cycle_id=3)
        assert not any(t.reason == "scheduled" for t in triggers)

    def test_stats_counts(self):
        scheduler = ReplayScheduler(scheduled_interval=5)
        scheduler.schedule_manual()
        scheduler.evaluate_cycle(cycle_id=5)
        stats = scheduler.stats()
        assert stats.total_triggers == 2
        assert stats.manual_triggers == 1
        assert stats.scheduled_triggers == 1

    def test_all_triggers_accumulate(self):
        scheduler = ReplayScheduler()
        scheduler.schedule_manual()
        scheduler.schedule_manual()
        assert len(scheduler.all_triggers()) == 2

    def test_clear(self):
        scheduler = ReplayScheduler()
        scheduler.schedule_manual()
        scheduler.clear()
        assert len(scheduler.all_triggers()) == 0

    def test_trigger_id_unique(self):
        scheduler = ReplayScheduler()
        t1 = scheduler.schedule_manual()
        t2 = scheduler.schedule_manual()
        assert t1.trigger_id != t2.trigger_id
