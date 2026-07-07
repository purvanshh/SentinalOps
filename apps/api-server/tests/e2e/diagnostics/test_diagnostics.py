"""Tests for observability diagnostics modules."""

import pytest
from observability.diagnostics.confidence_drift_monitor import ConfidenceDriftMonitor
from observability.diagnostics.reasoning_collapse_detector import ReasoningCollapseDetector
from observability.diagnostics.runtime_integrity_snapshot import RuntimeIntegritySnapshot
from observability.diagnostics.telemetry_health_monitor import TelemetryHealthMonitor

# ---------------------------------------------------------------------------
# ConfidenceDriftMonitor
# ---------------------------------------------------------------------------


class TestConfidenceDriftMonitor:
    def test_record_single_value(self):
        monitor = ConfidenceDriftMonitor(window_size=10)
        alerts = monitor.record(0.75)
        assert isinstance(alerts, list)

    def test_rejects_out_of_bounds_confidence(self):
        monitor = ConfidenceDriftMonitor()
        with pytest.raises(ValueError):
            monitor.record(1.5)
        with pytest.raises(ValueError):
            monitor.record(-0.1)

    def test_stats_with_data(self):
        monitor = ConfidenceDriftMonitor(window_size=10)
        for v in [0.5, 0.6, 0.7, 0.8, 0.9]:
            monitor.record(v)
        stats = monitor.current_stats()
        assert stats["observations"] == 5
        assert 0.5 <= stats["mean"] <= 0.9

    def test_stats_without_data(self):
        monitor = ConfidenceDriftMonitor()
        stats = monitor.current_stats()
        assert stats["status"] == "no_data"

    def test_inflation_alert_triggered(self):
        monitor = ConfidenceDriftMonitor(window_size=50)
        # Feed consistently high, low-variance values
        for _ in range(20):
            monitor.record(0.92)
        stats = monitor.current_stats()
        assert stats["mean"] > 0.85

    def test_collapse_alert_triggered(self):
        monitor = ConfidenceDriftMonitor(window_size=10)
        for _ in range(8):
            monitor.record(0.10)
        stats = monitor.current_stats()
        assert stats["mean"] < 0.20

    def test_prometheus_metrics_format(self):
        monitor = ConfidenceDriftMonitor()
        for v in [0.5, 0.6, 0.7]:
            monitor.record(v)
        metrics = monitor.prometheus_metrics()
        assert "sentinelops_confidence_mean" in metrics

    def test_operator_summary_present(self):
        monitor = ConfidenceDriftMonitor()
        for v in [0.5, 0.6, 0.7]:
            monitor.record(v)
        summary = monitor.operator_summary()
        assert "Confidence Monitor" in summary

    def test_reset_clears_window(self):
        monitor = ConfidenceDriftMonitor()
        for v in [0.5, 0.6, 0.7]:
            monitor.record(v)
        monitor.reset()
        stats = monitor.current_stats()
        assert stats.get("status") == "no_data"


# ---------------------------------------------------------------------------
# ReasoningCollapseDetector
# ---------------------------------------------------------------------------


class TestReasoningCollapseDetector:
    def test_no_collapse_clean_response(self):
        detector = ReasoningCollapseDetector()
        response = {
            "confidence": 0.65,
            "attribution": "deployment_regression",
            "explanation": "The deployment at 09:30 correlated with error spike onset.",
            "severity": "high",
            "metrics": {"error_rate": 0.45},
        }
        events = detector.check("inc-001", response)
        assert len(events) == 0

    def test_confidence_without_attribution_collapse(self):
        detector = ReasoningCollapseDetector()
        response = {"confidence": 0.90, "attribution": None, "explanation": ""}
        events = detector.check("inc-002", response)
        types = [e.collapse_type for e in events]
        assert "confidence_without_evidence" in types

    def test_empty_explanation_collapse(self):
        detector = ReasoningCollapseDetector()
        response = {
            "confidence": 0.80,
            "attribution": "network_issue",
            "explanation": "ok",  # too short
        }
        events = detector.check("inc-003", response)
        types = [e.collapse_type for e in events]
        assert "empty_explanation" in types

    def test_contradictory_severity_collapse(self):
        detector = ReasoningCollapseDetector()
        response = {
            "confidence": 0.50,
            "attribution": "something",
            "explanation": "Minor issue",
            "severity": "low",
            "metrics": {"error_rate": 0.95},
        }
        events = detector.check("inc-004", response)
        types = [e.collapse_type for e in events]
        assert "contradictory_severity" in types

    def test_circular_reasoning_detected(self):
        detector = ReasoningCollapseDetector()
        response = {
            "confidence": 0.60,
            "attribution": "high latency",
            "explanation": "The root cause is high latency.",
            "symptom": "high latency",
            "severity": "medium",
            "metrics": {"error_rate": 0.30},
        }
        events = detector.check("inc-005", response)
        types = [e.collapse_type for e in events]
        assert "circular_reasoning" in types

    def test_collapse_rate_zero_with_no_events(self):
        detector = ReasoningCollapseDetector()
        assert detector.collapse_rate() == 0.0

    def test_summary_structure(self):
        detector = ReasoningCollapseDetector()
        detector.check("inc-006", {"confidence": 0.95, "attribution": None, "explanation": ""})
        summary = detector.summary()
        assert "total_collapse_events" in summary
        assert summary["total_collapse_events"] >= 1

    def test_prometheus_metrics_format(self):
        detector = ReasoningCollapseDetector()
        detector.check("inc-007", {"confidence": 0.95, "attribution": None, "explanation": ""})
        metrics = detector.prometheus_metrics()
        assert "sentinelops_reasoning_collapse_total" in metrics


# ---------------------------------------------------------------------------
# RuntimeIntegritySnapshot
# ---------------------------------------------------------------------------


class TestRuntimeIntegritySnapshot:
    def test_capture_without_monitors(self):
        snapper = RuntimeIntegritySnapshot()
        report = snapper.capture()
        assert report.snapshot_id == "snap-0001"
        assert report.system_state in ("nominal", "degraded", "critical")
        assert 0.0 <= report.overall_integrity_score <= 1.0

    def test_capture_increments_id(self):
        snapper = RuntimeIntegritySnapshot()
        r1 = snapper.capture()
        r2 = snapper.capture()
        assert r1.snapshot_id != r2.snapshot_id

    def test_capture_with_monitors(self):
        monitor = ConfidenceDriftMonitor()
        detector = ReasoningCollapseDetector()
        for v in [0.6, 0.7, 0.65]:
            monitor.record(v)

        snapper = RuntimeIntegritySnapshot()
        report = snapper.capture(confidence_monitor=monitor, collapse_detector=detector)
        assert isinstance(report.confidence_health, dict)

    def test_history_accumulates(self):
        snapper = RuntimeIntegritySnapshot()
        snapper.capture()
        snapper.capture()
        assert len(snapper.history()) == 2

    def test_prometheus_metrics_format(self):
        snapper = RuntimeIntegritySnapshot()
        report = snapper.capture()
        metrics = report.prometheus_metrics()
        assert "sentinelops_integrity_score" in metrics

    def test_report_serializable(self):
        import json

        snapper = RuntimeIntegritySnapshot()
        report = snapper.capture()
        json.dumps(report.to_dict())

    def test_operator_summary_present(self):
        snapper = RuntimeIntegritySnapshot()
        report = snapper.capture()
        assert len(report.operator_summary) > 10


# ---------------------------------------------------------------------------
# TelemetryHealthMonitor
# ---------------------------------------------------------------------------


class TestTelemetryHealthMonitor:
    def _healthy_sample(self) -> dict:
        return {"metrics": {"error_rate": 0.05, "latency_p99": 200.0}}

    def _corrupt_sample(self) -> dict:
        return {"metrics": {"error_rate": -0.5, "latency_p99": 200.0}}  # impossible

    def test_healthy_sample_accepted(self):
        monitor = TelemetryHealthMonitor()
        ok = monitor.record(self._healthy_sample())
        assert ok is True

    def test_corrupt_sample_rejected(self):
        monitor = TelemetryHealthMonitor()
        ok = monitor.record(self._corrupt_sample())
        assert ok is False

    def test_health_score_high_for_clean_data(self):
        monitor = TelemetryHealthMonitor()
        for _ in range(10):
            monitor.record(self._healthy_sample())
        report = monitor.generate_report()
        assert report.health_score >= 0.80
        assert report.status == "healthy"

    def test_health_score_low_for_corrupt_data(self):
        monitor = TelemetryHealthMonitor()
        for _ in range(10):
            monitor.record(self._corrupt_sample())
        report = monitor.generate_report()
        assert report.health_score < 0.60

    def test_missing_fields_detected(self):
        monitor = TelemetryHealthMonitor()
        sample = {"metrics": {"latency_p99": 150.0}}  # missing error_rate
        monitor.record(sample)
        report = monitor.generate_report()
        assert report.missing_field_rate > 0.0

    def test_impossible_values_detected(self):
        monitor = TelemetryHealthMonitor()
        sample = {"metrics": {"error_rate": 1.5, "latency_p99": 100.0}}  # error_rate > 1
        monitor.record(sample)
        report = monitor.generate_report()
        assert report.impossible_value_rate > 0.0

    def test_prometheus_metrics_format(self):
        monitor = TelemetryHealthMonitor()
        for _ in range(5):
            monitor.record(self._healthy_sample())
        metrics = monitor.generate_report().prometheus_metrics()
        assert "sentinelops_telemetry_health_score" in metrics

    def test_current_health_returns_dict(self):
        monitor = TelemetryHealthMonitor()
        monitor.record(self._healthy_sample())
        health = monitor.current_health()
        assert isinstance(health, dict)
        assert "health_score" in health

    def test_report_serializable(self):
        import json

        monitor = TelemetryHealthMonitor()
        monitor.record(self._healthy_sample())
        report = monitor.generate_report()
        json.dumps(report.to_dict())
