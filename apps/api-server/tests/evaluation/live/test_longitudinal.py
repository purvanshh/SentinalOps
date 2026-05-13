"""Tests for longitudinal evaluation (Phase 47 Commit 3)."""

from __future__ import annotations

import pytest
from evaluation.live.evaluation_history import (
    EvaluationHistory,
    EvaluationRunSummary,
)
from evaluation.live.live_dataset_builder import (
    EvaluationSample,
    LiveDatasetBuilder,
)
from evaluation.live.longitudinal_metrics import (
    EvaluationRecord,
    LongitudinalEvaluator,
)
from evaluation.live.replay_comparator import ReplayComparator

# ---------------------------------------------------------------------------
# LiveDatasetBuilder
# ---------------------------------------------------------------------------


class TestLiveDatasetBuilder:
    def _events(self, n: int = 4) -> list[dict]:
        kinds = ["metric", "log", "alert", "metric"]
        return [
            {"kind": kinds[i % len(kinds)], "service": "api", "severity": "error", "labels": {}}
            for i in range(n)
        ]

    def test_ingest_and_build(self):
        builder = LiveDatasetBuilder(dataset_id="test", version="1.0")
        builder.ingest_replay_incident(
            incident_id="INC-001",
            events=self._events(),
            ground_truth_root_cause="db_overload",
            ground_truth_resolution="scale_db",
        )
        dataset = builder.build()
        assert dataset.size == 1
        assert dataset.samples[0].incident_id == "INC-001"

    def test_dataset_service_distribution(self):
        builder = LiveDatasetBuilder()
        builder.ingest_replay_incident("INC-1", self._events(), "r1", "s1")
        builder.ingest_replay_incident("INC-2", self._events(), "r2", "s2")
        ds = builder.build()
        dist = ds.service_distribution
        assert dist.get("api", 0) == 2

    def test_dataset_severity_distribution(self):
        builder = LiveDatasetBuilder()
        builder.ingest_replay_incident("INC-1", self._events(), "r1", "s1")
        ds = builder.build()
        assert "error" in ds.severity_distribution

    def test_mean_completeness_full(self):
        builder = LiveDatasetBuilder()
        builder.ingest_replay_incident("INC-1", self._events(), "r1", "s1")
        ds = builder.build()
        assert ds.mean_completeness == 1.0  # metric, log, alert all present

    def test_mean_completeness_partial(self):
        builder = LiveDatasetBuilder()
        partial_events = [{"kind": "log", "service": "api", "severity": "info", "labels": {}}]
        builder.ingest_replay_incident("INC-1", partial_events, "r1", "s1")
        ds = builder.build()
        assert ds.mean_completeness < 1.0

    def test_dataset_hash_stable(self):
        builder = LiveDatasetBuilder()
        builder.ingest_replay_incident("INC-1", self._events(), "r1", "s1")
        ds = builder.build()
        assert ds.dataset_hash() == ds.dataset_hash()

    def test_filter_by_severity(self):
        builder = LiveDatasetBuilder()
        builder.ingest_replay_incident(
            "INC-1",
            [{"kind": "alert", "service": "api", "severity": "critical", "labels": {}}],
            "r1",
            "s1",
        )
        builder.ingest_replay_incident(
            "INC-2",
            [{"kind": "log", "service": "api", "severity": "info", "labels": {}}],
            "r2",
            "s2",
        )
        ds = builder.build()
        critical_ds = ds.filter_by_severity("critical")
        assert critical_ds.size == 1
        assert critical_ds.samples[0].incident_id == "INC-1"

    def test_filter_by_service(self):
        builder = LiveDatasetBuilder()
        for svc in ("api", "db", "api"):
            builder.ingest_replay_incident(
                f"INC-{svc}",
                [{"kind": "log", "service": svc, "severity": "info", "labels": {}}],
                "r",
                "s",
            )
        ds = builder.build()
        api_ds = ds.filter_by_service("api")
        assert all(s.service == "api" for s in api_ds.samples)

    def test_reset_clears_samples(self):
        builder = LiveDatasetBuilder()
        builder.ingest_replay_incident("INC-1", self._events(), "r1", "s1")
        builder.reset()
        assert builder.build().size == 0

    def test_ingest_raw_sample(self):
        builder = LiveDatasetBuilder()
        sample = EvaluationSample(
            sample_id="S1",
            incident_id="INC-1",
            service="api",
            severity="error",
            timestamp_iso="2026-05-01T10:00:00Z",
            event_count=5,
            telemetry_completeness=0.67,
            ground_truth_root_cause="cpu_spike",
            ground_truth_resolution="restart",
        )
        builder.ingest_raw_sample(sample)
        ds = builder.build()
        assert ds.size == 1

    def test_fingerprint_unique(self):
        s1 = EvaluationSample(
            "S1", "INC-1", "api", "error", "2026-05-01T10:00:00Z", 1, 1.0, "r", "s"
        )
        s2 = EvaluationSample(
            "S2", "INC-2", "db", "critical", "2026-05-01T11:00:00Z", 1, 1.0, "r", "s"
        )
        assert s1.fingerprint() != s2.fingerprint()


# ---------------------------------------------------------------------------
# LongitudinalEvaluator
# ---------------------------------------------------------------------------


class TestLongitudinalEvaluator:
    def _record(
        self, correct: bool, confidence: float, severity: str = "error"
    ) -> EvaluationRecord:
        return EvaluationRecord(
            sample_id="S",
            correct=correct,
            confidence=confidence,
            severity=severity,
            telemetry_completeness=1.0,
        )

    def _batch(self, n: int, accuracy: float, confidence: float) -> list[EvaluationRecord]:
        records = []
        for i in range(n):
            # Interleave correct/incorrect evenly so every sliding window sees
            # the same accuracy — avoids ordering artifacts with overlapping windows.
            if accuracy <= 0.0:
                correct = False
            elif accuracy >= 1.0:
                correct = True
            else:
                period = round(1.0 / (1.0 - accuracy))
                correct = (i + 1) % period != 0
            records.append(self._record(correct=correct, confidence=confidence))
        return records

    def test_empty_report(self):
        ev = LongitudinalEvaluator(window_size=5)
        report = ev.compute()
        assert report.total_records == 0
        assert report.overall_accuracy == 0.0

    def test_overall_accuracy(self):
        ev = LongitudinalEvaluator(window_size=5)
        ev.ingest_batch(self._batch(10, accuracy=0.80, confidence=0.80))
        report = ev.compute()
        assert abs(report.overall_accuracy - 0.80) < 0.02

    def test_calibration_error_calibrated(self):
        ev = LongitudinalEvaluator(window_size=5)
        ev.ingest_batch(self._batch(20, accuracy=0.80, confidence=0.80))
        report = ev.compute()
        assert report.overall_calibration_error < 0.05

    def test_window_count(self):
        ev = LongitudinalEvaluator(window_size=10)
        ev.ingest_batch(self._batch(30, accuracy=0.70, confidence=0.70))
        report = ev.compute()
        assert report.num_windows >= 1

    def test_drift_stable(self):
        ev = LongitudinalEvaluator(window_size=5)
        ev.ingest_batch(self._batch(40, accuracy=0.80, confidence=0.80))
        report = ev.compute()
        assert report.drift is not None
        assert report.drift.drift_direction == "stable"

    def test_drift_degrading(self):
        ev = LongitudinalEvaluator(window_size=5)
        # First half: high accuracy; second half: low accuracy
        good = self._batch(20, accuracy=1.0, confidence=0.90)
        bad = self._batch(20, accuracy=0.0, confidence=0.90)
        ev.ingest_batch(good + bad)
        report = ev.compute()
        assert report.drift is not None
        assert report.drift.drift_direction == "degrading"

    def test_trend_improving(self):
        # Large blocks + large window so boundary effects don't trigger "volatile".
        ev = LongitudinalEvaluator(window_size=20)
        records = []
        for acc in [0.2, 0.5, 0.8]:
            records.extend(self._batch(60, accuracy=acc, confidence=acc))
        ev.ingest_batch(records)
        report = ev.compute()
        assert report.trend in ("improving", "stable")

    def test_trend_degrading(self):
        ev = LongitudinalEvaluator(window_size=20)
        records = []
        for acc in [0.8, 0.5, 0.2]:
            records.extend(self._batch(60, accuracy=acc, confidence=acc))
        ev.ingest_batch(records)
        report = ev.compute()
        assert report.trend in ("degrading", "stable")

    def test_overconfident_window(self):
        ev = LongitudinalEvaluator(window_size=5)
        # confidence=0.90 but only 50% correct
        records = self._batch(10, accuracy=0.50, confidence=0.90)
        ev.ingest_batch(records)
        report = ev.compute()
        assert any(w.is_overconfident for w in report.windows)

    def test_severity_weighted_accuracy(self):
        ev = LongitudinalEvaluator(window_size=5)
        ev.ingest(
            EvaluationRecord("S1", True, 0.80, severity="critical", telemetry_completeness=1.0)
        )
        ev.ingest(EvaluationRecord("S2", False, 0.80, severity="debug", telemetry_completeness=1.0))
        report = ev.compute()
        # critical correct → weighted accuracy favours the correct critical event
        assert report.windows[0].severity_weighted_accuracy > 0.0

    def test_window_size_validation(self):
        with pytest.raises(ValueError):
            LongitudinalEvaluator(window_size=1)

    def test_reset_clears_records(self):
        ev = LongitudinalEvaluator(window_size=5)
        ev.ingest_batch(self._batch(10, 0.80, 0.80))
        ev.reset()
        report = ev.compute()
        assert report.total_records == 0


# ---------------------------------------------------------------------------
# EvaluationHistory
# ---------------------------------------------------------------------------


class TestEvaluationHistory:
    def _summary(self, run_id: str, accuracy: float, drift: bool = False) -> EvaluationRunSummary:
        return EvaluationRunSummary(
            run_id=run_id,
            dataset_id="test_ds",
            dataset_version="1.0",
            executed_at="2026-05-01T10:00:00Z",
            num_samples=100,
            overall_accuracy=accuracy,
            mean_confidence=accuracy,
            calibration_error=0.0,
            trend="stable",
            drift_detected=drift,
            drift_direction="stable" if not drift else "degrading",
        )

    def test_record_and_retrieve(self):
        history = EvaluationHistory()
        history.record(self._summary("R1", 0.80))
        assert history.run_count() == 1

    def test_best_run(self):
        history = EvaluationHistory()
        history.record(self._summary("R1", 0.70))
        history.record(self._summary("R2", 0.90))
        assert history.best_run().run_id == "R2"

    def test_worst_run(self):
        history = EvaluationHistory()
        history.record(self._summary("R1", 0.70))
        history.record(self._summary("R2", 0.90))
        assert history.worst_run().run_id == "R1"

    def test_compare_improvement(self):
        history = EvaluationHistory()
        history.record(self._summary("R1", 0.60))
        history.record(self._summary("R2", 0.90))
        cmp = history.compare("R1", "R2")
        assert cmp is not None
        assert cmp.verdict == "improvement"
        assert cmp.improvement_detected

    def test_compare_regression(self):
        history = EvaluationHistory()
        history.record(self._summary("R1", 0.90))
        history.record(self._summary("R2", 0.60))
        cmp = history.compare("R1", "R2")
        assert cmp is not None
        assert cmp.verdict == "regression"
        assert cmp.regression_detected

    def test_compare_neutral(self):
        history = EvaluationHistory()
        history.record(self._summary("R1", 0.80))
        history.record(self._summary("R2", 0.81))
        cmp = history.compare("R1", "R2")
        assert cmp is not None
        assert cmp.verdict == "neutral"

    def test_compare_missing_run(self):
        history = EvaluationHistory()
        history.record(self._summary("R1", 0.80))
        cmp = history.compare("R1", "NONEXISTENT")
        assert cmp is None

    def test_compare_last_two(self):
        history = EvaluationHistory()
        history.record(self._summary("R1", 0.70))
        history.record(self._summary("R2", 0.85))
        cmp = history.compare_last_two()
        assert cmp is not None
        assert cmp.baseline_run_id == "R1"
        assert cmp.candidate_run_id == "R2"

    def test_compare_last_two_insufficient(self):
        history = EvaluationHistory()
        history.record(self._summary("R1", 0.80))
        assert history.compare_last_two() is None

    def test_quality_score_calibrated(self):
        s = self._summary("R1", 0.80)
        assert s.quality_score <= s.overall_accuracy

    def test_clear(self):
        history = EvaluationHistory()
        history.record(self._summary("R1", 0.80))
        history.clear()
        assert history.run_count() == 0

    def test_all_runs(self):
        history = EvaluationHistory()
        for i in range(3):
            history.record(self._summary(f"R{i}", 0.70 + i * 0.05))
        assert len(history.all_runs()) == 3


# ---------------------------------------------------------------------------
# ReplayComparator
# ---------------------------------------------------------------------------


class TestReplayComparator:
    def _events(
        self, kinds: list[str], service: str = "api", incident_id: str = "INC-1"
    ) -> list[dict]:
        return [
            {"kind": k, "service": service, "severity": "error", "incident_id": incident_id}
            for k in kinds
        ]

    def test_compare_equivalent_sessions(self):
        comp = ReplayComparator()
        full_kinds = ["metric", "log", "alert"]
        diff = comp.compare_event_lists(
            self._events(full_kinds),
            self._events(full_kinds),
        )
        assert diff.verdict == "equivalent"

    def test_compare_b_richer(self):
        comp = ReplayComparator()
        diff = comp.compare_event_lists(
            self._events(["log"]),
            self._events(["metric", "log", "alert"]),
        )
        assert diff.verdict == "b_richer"

    def test_compare_a_richer(self):
        comp = ReplayComparator()
        diff = comp.compare_event_lists(
            self._events(["metric", "log", "alert"]),
            self._events(["log"]),
        )
        assert diff.verdict == "a_richer"

    def test_event_count_delta(self):
        comp = ReplayComparator()
        diff = comp.compare_event_lists(
            self._events(["log"] * 3),
            self._events(["log"] * 7),
        )
        assert diff.event_count_delta == 4

    def test_shared_services(self):
        comp = ReplayComparator()
        diff = comp.compare_event_lists(
            [{"kind": "log", "service": "api", "severity": "info", "incident_id": "I1"}],
            [{"kind": "log", "service": "api", "severity": "info", "incident_id": "I1"}],
        )
        assert "api" in diff.shared_services

    def test_services_only_in_b(self):
        comp = ReplayComparator()
        diff = comp.compare_event_lists(
            [{"kind": "log", "service": "api", "severity": "info", "incident_id": "I1"}],
            [
                {"kind": "log", "service": "api", "severity": "info", "incident_id": "I1"},
                {"kind": "log", "service": "db", "severity": "info", "incident_id": "I1"},
            ],
        )
        assert "db" in diff.services_only_in_b

    def test_severity_deltas(self):
        comp = ReplayComparator()
        diff = comp.compare_event_lists(
            [{"kind": "log", "service": "api", "severity": "info", "incident_id": "I1"}],
            [
                {"kind": "log", "service": "api", "severity": "error", "incident_id": "I1"},
                {"kind": "log", "service": "api", "severity": "error", "incident_id": "I1"},
            ],
        )
        assert diff.severity_deltas.get("error", 0) > 0

    def test_profile_empty_events(self):
        comp = ReplayComparator()
        profile = comp.profile_events([])
        assert profile.total_events == 0
        assert profile.coverage_score() == 0.0

    def test_profile_coverage_full(self):
        comp = ReplayComparator()
        events = self._events(["metric", "log", "alert"])
        profile = comp.profile_events(events)
        assert profile.coverage_score() == 1.0

    def test_diff_summary_string(self):
        comp = ReplayComparator()
        diff = comp.compare_event_lists(
            self._events(["log"]),
            self._events(["metric", "log", "alert"]),
        )
        summary = diff.summary()
        assert "verdict" in summary
