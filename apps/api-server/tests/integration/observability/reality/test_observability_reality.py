"""Tests for Phase 48 observability reality modules."""

from __future__ import annotations

from observability.reality.completeness_analyzer import CompletenessAnalyzer
from observability.reality.confidence_penalties import ConfidencePenaltyCalculator
from observability.reality.observability_gaps import GapKind, ObservabilityGapDetector
from observability.reality.telemetry_integrity import TelemetryIntegrityChecker

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _full_events() -> list[dict]:
    """A complete, clean set of events."""
    return [
        {
            "event_id": f"e{i}",
            "kind": k,
            "timestamp_iso": f"2026-05-14T10:0{i}:00Z",
            "service": "api-gw",
            "severity": s,
            "payload": {"val": i},
            "sequence_number": i,
        }
        for i, (k, s) in enumerate(
            [
                ("metric", "warning"),
                ("log", "error"),
                ("alert", "critical"),
            ]
        )
    ]


# ---------------------------------------------------------------------------
# CompletenessAnalyzer
# ---------------------------------------------------------------------------


class TestCompletenessAnalyzer:
    def test_full_events_score_near_one(self):
        score = CompletenessAnalyzer().analyze(_full_events())
        assert score.overall >= 0.80

    def test_empty_events_score_zero(self):
        score = CompletenessAnalyzer().analyze([])
        assert score.overall == 0.0

    def test_missing_alert_reduces_kind_coverage(self):
        events = [e for e in _full_events() if e["kind"] != "alert"]
        score = CompletenessAnalyzer().analyze(events)
        assert score.kind_coverage < 1.0

    def test_missing_severity_levels_reduce_coverage(self):
        events = [
            {
                "event_id": "e0",
                "kind": "metric",
                "severity": "info",
                "service": "svc",
                "timestamp_iso": "2026-05-14T10:00:00Z",
                "payload": {},
            }
        ]
        score = CompletenessAnalyzer().analyze(events)
        assert score.severity_coverage == 0.0

    def test_invalid_timestamps_reduce_validity(self):
        events = [
            {
                "event_id": "e0",
                "kind": "metric",
                "severity": "error",
                "service": "svc",
                "timestamp_iso": "not-a-date",
                "payload": {},
            },
        ]
        score = CompletenessAnalyzer().analyze(events)
        assert score.timestamp_validity == 0.0

    def test_missing_service_reduces_coverage(self):
        events = [
            {
                "event_id": "e0",
                "kind": "alert",
                "severity": "critical",
                "service": "",
                "timestamp_iso": "2026-05-14T10:00:00Z",
                "payload": {},
            }
        ]
        score = CompletenessAnalyzer().analyze(events)
        assert score.service_coverage == 0.0

    def test_to_dict(self):
        score = CompletenessAnalyzer().analyze(_full_events())
        d = score.to_dict()
        assert "overall" in d
        assert "kind_coverage" in d


# ---------------------------------------------------------------------------
# ObservabilityGapDetector
# ---------------------------------------------------------------------------


class TestObservabilityGapDetector:
    def test_full_events_no_gaps(self):
        report = ObservabilityGapDetector().detect(_full_events())
        kinds = {g.kind for g in report.gaps}
        assert GapKind.MISSING_METRICS not in kinds
        assert GapKind.MISSING_LOGS not in kinds
        assert GapKind.MISSING_ALERTS not in kinds

    def test_missing_metric_gap_detected(self):
        events = [e for e in _full_events() if e["kind"] != "metric"]
        report = ObservabilityGapDetector().detect(events)
        assert any(g.kind == GapKind.MISSING_METRICS for g in report.gaps)

    def test_missing_log_gap_detected(self):
        events = [e for e in _full_events() if e["kind"] != "log"]
        report = ObservabilityGapDetector().detect(events)
        assert any(g.kind == GapKind.MISSING_LOGS for g in report.gaps)

    def test_missing_alert_gap_detected(self):
        events = [e for e in _full_events() if e["kind"] != "alert"]
        report = ObservabilityGapDetector().detect(events)
        assert any(g.kind == GapKind.MISSING_ALERTS for g in report.gaps)

    def test_stale_replay_gap_detected(self):
        events = [
            {
                "event_id": f"e{i}",
                "kind": "metric",
                "timestamp_iso": "2026-05-14T10:00:00Z",
                "service": "svc",
                "severity": "warning",
                "payload": {},
                "_stale_replay": True,
            }
            for i in range(5)
        ]
        report = ObservabilityGapDetector().detect(events)
        assert any(g.kind == GapKind.STALE_REPLAY for g in report.gaps)

    def test_duplicate_flood_detected(self):
        events = [
            {
                "event_id": f"e{i}",
                "kind": "alert",
                "timestamp_iso": "2026-05-14T10:00:00Z",
                "service": "svc",
                "severity": "critical",
                "payload": {},
                "_duplicate": True,
            }
            for i in range(4)
        ] + [
            {
                "event_id": "real",
                "kind": "metric",
                "timestamp_iso": "2026-05-14T10:01:00Z",
                "service": "svc",
                "severity": "warning",
                "payload": {},
            }
        ]
        report = ObservabilityGapDetector().detect(events)
        assert any(g.kind == GapKind.DUPLICATE_FLOOD for g in report.gaps)

    def test_blackout_window_detected(self):
        events = [
            {
                "event_id": "e0",
                "kind": "metric",
                "timestamp_iso": "2026-05-14T10:00:00Z",
                "service": "svc",
                "severity": "warning",
                "payload": {},
            },
            {
                "event_id": "e1",
                "kind": "alert",
                "timestamp_iso": "2026-05-14T11:00:00Z",  # 60-min gap
                "service": "svc",
                "severity": "critical",
                "payload": {},
            },
        ]
        report = ObservabilityGapDetector().detect(events)
        assert any(g.kind == GapKind.TELEMETRY_BLACKOUT for g in report.gaps)

    def test_penalty_capped_at_0_60(self):
        # All gaps present
        events = []  # empty → all gaps
        report = ObservabilityGapDetector().detect(events)
        assert report.total_confidence_penalty <= 0.60

    def test_to_dict(self):
        report = ObservabilityGapDetector().detect(_full_events())
        d = report.to_dict()
        assert "gap_count" in d


# ---------------------------------------------------------------------------
# TelemetryIntegrityChecker
# ---------------------------------------------------------------------------


class TestTelemetryIntegrityChecker:
    def test_clean_events_high_integrity(self):
        report = TelemetryIntegrityChecker().check(_full_events())
        assert report.integrity_score >= 0.70

    def test_empty_events_zero_integrity(self):
        report = TelemetryIntegrityChecker().check([])
        assert report.integrity_score == 0.0

    def test_out_of_order_timestamp_detected(self):
        events = [
            {
                "event_id": "e0",
                "kind": "metric",
                "timestamp_iso": "2026-05-14T10:05:00Z",
                "service": "svc",
                "severity": "warning",
                "payload": {},
                "sequence_number": 0,
            },
            {
                "event_id": "e1",
                "kind": "log",
                "timestamp_iso": "2026-05-14T10:00:00Z",
                "service": "svc",
                "severity": "error",
                "payload": {},
                "sequence_number": 1,
            },
        ]
        report = TelemetryIntegrityChecker().check(events)
        types = [v.violation_type for v in report.violations]
        assert "out_of_order_timestamp" in types

    def test_severity_contradiction_detected(self):
        events = [
            {
                "event_id": "e0",
                "kind": "metric",
                "timestamp_iso": "2026-05-14T10:00:00Z",
                "service": "svc",
                "severity": "warning",
                "payload": {},
            },
            {
                "event_id": "e0",
                "kind": "metric",
                "timestamp_iso": "2026-05-14T10:01:00Z",
                "service": "svc",
                "severity": "critical",
                "payload": {},
            },
        ]
        report = TelemetryIntegrityChecker().check(events)
        assert report.contradictions_found

    def test_clock_skew_detected(self):
        events = [
            {
                "event_id": "e0",
                "kind": "metric",
                "timestamp_iso": "2026-05-14T10:00:00Z",
                "service": "svc-a",
                "severity": "warning",
                "payload": {},
            },
            {
                "event_id": "e1",
                "kind": "log",
                "timestamp_iso": "2026-05-14T11:30:00Z",
                "service": "svc-b",
                "severity": "error",
                "payload": {},
            },
        ]
        report = TelemetryIntegrityChecker().check(events)
        assert report.clock_skew_detected

    def test_to_dict(self):
        report = TelemetryIntegrityChecker().check(_full_events())
        d = report.to_dict()
        assert "integrity_score" in d


# ---------------------------------------------------------------------------
# ConfidencePenaltyCalculator
# ---------------------------------------------------------------------------


class TestConfidencePenaltyCalculator:
    def test_clean_telemetry_minimal_penalty(self):
        calc = ConfidencePenaltyCalculator()
        breakdown = calc.compute_from_events(0.80, _full_events())
        assert breakdown.total_penalty < 0.20
        assert breakdown.penalised_confidence > 0.60

    def test_empty_telemetry_large_penalty(self):
        calc = ConfidencePenaltyCalculator()
        breakdown = calc.compute_from_events(0.80, [])
        assert breakdown.total_penalty >= 0.30

    def test_penalty_never_exceeds_0_60(self):
        calc = ConfidencePenaltyCalculator()
        breakdown = calc.compute_from_events(0.90, [])
        assert breakdown.total_penalty <= 0.60

    def test_penalised_confidence_floored_at_0_05(self):
        calc = ConfidencePenaltyCalculator()
        breakdown = calc.compute_from_events(0.10, [])
        assert breakdown.penalised_confidence >= 0.05

    def test_should_refuse_attribution_when_very_low(self):
        calc = ConfidencePenaltyCalculator()
        breakdown = calc.compute_from_events(0.15, [])
        assert breakdown.should_refuse_attribution

    def test_should_not_refuse_for_high_confidence_clean(self):
        calc = ConfidencePenaltyCalculator()
        breakdown = calc.compute_from_events(0.90, _full_events())
        assert not breakdown.should_refuse_attribution

    def test_to_dict(self):
        calc = ConfidencePenaltyCalculator()
        breakdown = calc.compute_from_events(0.80, _full_events())
        d = breakdown.to_dict()
        assert "total_penalty" in d
        assert "penalised_confidence" in d
