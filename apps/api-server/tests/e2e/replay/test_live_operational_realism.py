"""
Operational realism benchmark suite (Phase 47 Commit 7).

Loads the 25 realistic live_replay incidents from simulation/datasets/live_replay/
and validates that the telemetry replay, normalization, and longitudinal evaluation
pipeline produces operationally realistic results.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from evaluation.live.live_dataset_builder import LiveDatasetBuilder
from evaluation.live.longitudinal_metrics import EvaluationRecord, LongitudinalEvaluator
from evaluation.live.replay_comparator import ReplayComparator
from ingestion.telemetry_normalizer import TelemetryNormalizer, UnifiedTelemetryEvent
from replay import timeline_reconstructor
from replay.replay_models import EventKind, TelemetryEvent

# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

INCIDENTS_PATH = (
    Path(__file__).parents[4] / "simulation" / "datasets" / "live_replay" / "incidents.json"
)


@pytest.fixture(scope="module")
def incident_records():
    with open(INCIDENTS_PATH) as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Dataset completeness
# ---------------------------------------------------------------------------


class TestLiveReplayDataset:
    def test_dataset_has_25_incidents(self, incident_records):
        assert len(incident_records) == 25

    def test_all_incidents_have_required_fields(self, incident_records):
        required = {"incident_id", "ground_truth_root_cause", "ground_truth_resolution", "events"}
        for rec in incident_records:
            assert required <= set(rec.keys()), f"Missing fields in {rec.get('incident_id')}"

    def test_all_incidents_have_events(self, incident_records):
        for rec in incident_records:
            assert len(rec["events"]) >= 2, f"{rec['incident_id']} has too few events"

    def test_event_kinds_valid(self, incident_records):
        valid_kinds = {"metric", "log", "alert", "deployment", "topology_change"}
        for rec in incident_records:
            for ev in rec["events"]:
                assert ev["kind"] in valid_kinds, (
                    f"Invalid kind '{ev['kind']}' in {rec['incident_id']}"
                )

    def test_all_incidents_have_unique_ids(self, incident_records):
        ids = [r["incident_id"] for r in incident_records]
        assert len(ids) == len(set(ids))

    def test_root_causes_are_diverse(self, incident_records):
        root_causes = {r["ground_truth_root_cause"] for r in incident_records}
        assert len(root_causes) == 25

    def test_severities_cover_all_levels(self, incident_records):
        severities = set()
        for rec in incident_records:
            for ev in rec["events"]:
                severities.add(ev.get("severity", ""))
        assert "critical" in severities
        assert "error" in severities
        assert "warning" in severities

    def test_service_diversity(self, incident_records):
        services = set()
        for rec in incident_records:
            for ev in rec["events"]:
                svc = ev.get("service", "")
                if svc:
                    services.add(svc)
        assert len(services) >= 5


# ---------------------------------------------------------------------------
# TelemetryNormalizer against live replay incidents
# ---------------------------------------------------------------------------


class TestNormalizationOnLiveData:
    def test_all_events_normalize_without_error(self, incident_records):
        normalizer = TelemetryNormalizer()
        total = 0
        success = 0
        for rec in incident_records:
            for ev in rec["events"]:
                raw = dict(ev)
                raw["event_id"] = f"{rec['incident_id']}_{total}"
                raw["incident_id"] = rec["incident_id"]
                result = normalizer.normalize(raw, source_kind="live_replay")
                if isinstance(result, UnifiedTelemetryEvent):
                    success += 1
                total += 1
        assert success / total >= 0.95

    def test_batch_normalization_success_rate(self, incident_records):
        normalizer = TelemetryNormalizer()
        batch = []
        for rec in incident_records:
            for i, ev in enumerate(rec["events"]):
                raw = dict(ev)
                raw["event_id"] = f"{rec['incident_id']}_{i}"
                raw["incident_id"] = rec["incident_id"]
                batch.append(raw)
        result = normalizer.normalize_batch(batch, source_kind="live_replay")
        assert result.success_rate >= 0.95

    def test_ingestion_confidence_reasonable(self, incident_records):
        normalizer = TelemetryNormalizer()
        confidences = []
        for rec in incident_records[:10]:
            for i, ev in enumerate(rec["events"]):
                raw = dict(ev)
                raw["event_id"] = f"{rec['incident_id']}_{i}"
                raw["message"] = f"event from {rec['incident_id']}"
                result = normalizer.normalize(raw, source_kind="live_replay")
                if isinstance(result, UnifiedTelemetryEvent):
                    confidences.append(result.ingestion_confidence)
        assert len(confidences) > 0
        assert sum(confidences) / len(confidences) >= 0.40


# ---------------------------------------------------------------------------
# Timeline reconstruction on live replay incidents
# ---------------------------------------------------------------------------


class TestTimelineReconstructionOnLiveData:
    def _make_telemetry_events(self, rec: dict) -> list[TelemetryEvent]:
        events = []
        for i, ev in enumerate(rec["events"]):
            try:
                kind = EventKind(ev["kind"])
            except ValueError:
                kind = EventKind.LOG
            events.append(
                TelemetryEvent(
                    event_id=f"{rec['incident_id']}_{i}",
                    kind=kind,
                    timestamp_iso=f"2026-05-14T10:{i:02d}:00Z",
                    service=ev.get("service", "unknown"),
                    payload=ev,
                    severity=ev.get("severity", "info"),
                    labels=ev.get("labels", {}),
                    incident_id=rec["incident_id"],
                    sequence_number=i,
                )
            )
        return events

    def test_reconstruct_all_incidents(self, incident_records):
        for rec in incident_records:
            events = self._make_telemetry_events(rec)
            tl = timeline_reconstructor.reconstruct_incident(rec["incident_id"], events)
            assert tl.incident_id == rec["incident_id"]
            assert tl.event_count == len(events)

    def test_critical_transitions_detected(self, incident_records):
        incidents_with_transitions = 0
        for rec in incident_records:
            events = self._make_telemetry_events(rec)
            tl = timeline_reconstructor.reconstruct_incident(rec["incident_id"], events)
            if tl.critical_transitions:
                incidents_with_transitions += 1
        assert incidents_with_transitions >= 20

    def test_telemetry_completeness_scores(self, incident_records):
        scores = []
        for rec in incident_records:
            events = self._make_telemetry_events(rec)
            tl = timeline_reconstructor.reconstruct_incident(rec["incident_id"], events)
            scores.append(tl.telemetry_completeness)
        mean_completeness = sum(scores) / len(scores)
        assert mean_completeness >= 0.50


# ---------------------------------------------------------------------------
# LiveDatasetBuilder on live replay incidents
# ---------------------------------------------------------------------------


class TestLiveDatasetBuilderOnRealData:
    def test_build_full_dataset(self, incident_records):
        builder = LiveDatasetBuilder(dataset_id="live_replay_benchmark", version="1.0")
        for rec in incident_records:
            builder.ingest_replay_incident(
                incident_id=rec["incident_id"],
                events=rec["events"],
                ground_truth_root_cause=rec["ground_truth_root_cause"],
                ground_truth_resolution=rec["ground_truth_resolution"],
            )
        dataset = builder.build()
        assert dataset.size == 25

    def test_mean_completeness_acceptable(self, incident_records):
        builder = LiveDatasetBuilder()
        for rec in incident_records:
            builder.ingest_replay_incident(
                incident_id=rec["incident_id"],
                events=rec["events"],
                ground_truth_root_cause=rec["ground_truth_root_cause"],
                ground_truth_resolution=rec["ground_truth_resolution"],
            )
        dataset = builder.build()
        assert dataset.mean_completeness >= 0.50

    def test_dataset_severity_distribution_has_critical(self, incident_records):
        builder = LiveDatasetBuilder()
        for rec in incident_records:
            builder.ingest_replay_incident(
                incident_id=rec["incident_id"],
                events=rec["events"],
                ground_truth_root_cause=rec["ground_truth_root_cause"],
                ground_truth_resolution=rec["ground_truth_resolution"],
            )
        dataset = builder.build()
        sev_dist = dataset.severity_distribution
        assert "critical" in sev_dist or "error" in sev_dist

    def test_dataset_hash_is_stable(self, incident_records):
        builder = LiveDatasetBuilder()
        for rec in incident_records:
            builder.ingest_replay_incident(
                incident_id=rec["incident_id"],
                events=rec["events"],
                ground_truth_root_cause=rec["ground_truth_root_cause"],
                ground_truth_resolution=rec["ground_truth_resolution"],
            )
        dataset = builder.build()
        assert dataset.dataset_hash() == dataset.dataset_hash()


# ---------------------------------------------------------------------------
# ReplayComparator on live replay dataset
# ---------------------------------------------------------------------------


class TestReplayComparatorOnLiveData:
    def _all_events(self, incident_records) -> list[dict]:
        events = []
        for rec in incident_records:
            events.extend(rec["events"])
        return events

    def test_profile_live_dataset(self, incident_records):
        comp = ReplayComparator()
        events = self._all_events(incident_records)
        profile = comp.profile_events(events, session_hash="live_replay_v1")
        assert profile.total_events == len(events)
        assert profile.coverage_score() > 0.0

    def test_coverage_score_at_least_half(self, incident_records):
        comp = ReplayComparator()
        events = self._all_events(incident_records)
        profile = comp.profile_events(events)
        assert profile.coverage_score() >= 0.50

    def test_compare_first_half_vs_second_half(self, incident_records):
        comp = ReplayComparator()
        mid = len(incident_records) // 2
        events_a = []
        for rec in incident_records[:mid]:
            events_a.extend(rec["events"])
        events_b = []
        for rec in incident_records[mid:]:
            events_b.extend(rec["events"])
        diff = comp.compare_event_lists(events_a, events_b)
        assert diff.verdict in ("equivalent", "a_richer", "b_richer", "divergent")


# ---------------------------------------------------------------------------
# End-to-end longitudinal evaluation on simulated benchmark records
# ---------------------------------------------------------------------------


class TestLongitudinalEvalOnLiveData:
    def test_evaluator_with_all_incidents(self, incident_records):
        evaluator = LongitudinalEvaluator(window_size=5)
        for i, rec in enumerate(incident_records):
            correct = i % 4 != 0  # 75% accuracy
            evaluator.ingest(
                EvaluationRecord(
                    sample_id=rec["incident_id"],
                    correct=correct,
                    confidence=0.78 if correct else 0.55,
                    severity="error",
                    telemetry_completeness=1.0,
                )
            )
        report = evaluator.compute()
        assert report.total_records == 25
        assert report.overall_accuracy >= 0.60

    def test_no_volatile_trend_with_stable_accuracy(self, incident_records):
        evaluator = LongitudinalEvaluator(window_size=5)
        for rec in incident_records:
            evaluator.ingest(
                EvaluationRecord(
                    sample_id=rec["incident_id"],
                    correct=True,
                    confidence=0.85,
                    severity="error",
                    telemetry_completeness=1.0,
                )
            )
        report = evaluator.compute()
        assert report.trend in ("stable", "improving")
        assert report.overall_accuracy == 1.0
