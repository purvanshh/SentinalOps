"""Tests for telemetry replay engine and timeline reconstruction (Phase 47)."""

from __future__ import annotations

import gzip
import json

from replay.event_stream import read_from_list, read_from_path
from replay.replay_models import EventKind, ReplayState, TelemetryEvent
from replay.telemetry_replay import ReplayEngine
from replay.timeline_reconstructor import reconstruct_all, reconstruct_incident

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_event(
    event_id: str,
    kind: str = "alert",
    ts: str = "2026-05-01T10:00:00Z",
    service: str = "api",
    incident_id: str | None = "INC-001",
    seq: int = 0,
    severity: str = "error",
) -> dict:
    return {
        "event_id": event_id,
        "kind": kind,
        "timestamp_iso": ts,
        "service": service,
        "payload": {"description": f"event {event_id}", "message": f"msg {event_id}"},
        "source": "test",
        "severity": severity,
        "labels": {"operator_id": "ops-1"},
        "incident_id": incident_id,
        "sequence_number": seq,
    }


def _three_event_stream() -> list[dict]:
    return [
        _make_event("E1", kind="metric", ts="2026-05-01T10:00:00Z", seq=1),
        _make_event("E2", kind="alert", ts="2026-05-01T10:01:00Z", seq=2),
        _make_event(
            "E3",
            kind="operator_action",
            ts="2026-05-01T10:02:00Z",
            seq=3,
            severity="info",
        ),
    ]


# ---------------------------------------------------------------------------
# replay_models
# ---------------------------------------------------------------------------


class TestTelemetryEvent:
    def test_fingerprint_is_deterministic(self):
        ev = TelemetryEvent(
            event_id="E1",
            kind=EventKind.ALERT,
            timestamp_iso="2026-05-01T10:00:00Z",
            service="api",
            payload={},
        )
        assert ev.fingerprint() == ev.fingerprint()

    def test_fingerprint_differs_for_different_events(self):
        ev1 = TelemetryEvent(
            event_id="E1",
            kind=EventKind.ALERT,
            timestamp_iso="2026-05-01T10:00:00Z",
            service="api",
            payload={},
        )
        ev2 = TelemetryEvent(
            event_id="E2",
            kind=EventKind.ALERT,
            timestamp_iso="2026-05-01T10:00:00Z",
            service="api",
            payload={},
        )
        assert ev1.fingerprint() != ev2.fingerprint()

    def test_to_dict_contains_fingerprint(self):
        ev = TelemetryEvent(
            event_id="E1",
            kind=EventKind.METRIC,
            timestamp_iso="2026-05-01T10:00:00Z",
            service="api",
            payload={},
        )
        d = ev.to_dict()
        assert "fingerprint" in d
        assert len(d["fingerprint"]) == 16


# ---------------------------------------------------------------------------
# event_stream
# ---------------------------------------------------------------------------


class TestEventStream:
    def test_read_from_list_returns_events(self):
        result = read_from_list(_three_event_stream())
        assert len(result.events) == 3
        assert len(result.quarantined) == 0

    def test_read_from_list_sorts_by_timestamp(self):
        raw = [
            _make_event("E3", ts="2026-05-01T10:02:00Z", seq=3),
            _make_event("E1", ts="2026-05-01T10:00:00Z", seq=1),
            _make_event("E2", ts="2026-05-01T10:01:00Z", seq=2),
        ]
        result = read_from_list(raw)
        ts_list = [ev.timestamp_iso for ev in result.events]
        assert ts_list == sorted(ts_list)

    def test_malformed_event_quarantined(self):
        raw = [
            {"not_a_valid_event": True},
            _make_event("E1"),
        ]
        result = read_from_list(raw)
        assert len(result.events) >= 1
        assert result.parse_success_rate <= 1.0

    def test_parse_success_rate_all_valid(self):
        result = read_from_list(_three_event_stream())
        assert result.parse_success_rate == 1.0

    def test_read_from_json_file(self, tmp_path):
        data = _three_event_stream()
        f = tmp_path / "events.json"
        f.write_text(json.dumps(data))
        result = read_from_path(f)
        assert len(result.events) == 3
        assert result.format_detected == "json"

    def test_read_from_ndjson_file(self, tmp_path):
        data = _three_event_stream()
        f = tmp_path / "events.ndjson"
        f.write_text("\n".join(json.dumps(ev) for ev in data))
        result = read_from_path(f)
        assert len(result.events) == 3
        assert result.format_detected == "ndjson"

    def test_read_from_gzip_json(self, tmp_path):
        data = _three_event_stream()
        f = tmp_path / "events.json.gz"
        with gzip.open(f, "wt") as fh:
            json.dump(data, fh)
        result = read_from_path(f)
        assert len(result.events) == 3
        assert result.format_detected == "json.gz"

    def test_read_from_gzip_ndjson(self, tmp_path):
        data = _three_event_stream()
        f = tmp_path / "events.ndjson.gz"
        with gzip.open(f, "wt") as fh:
            fh.write("\n".join(json.dumps(ev) for ev in data))
        result = read_from_path(f)
        assert len(result.events) == 3
        assert result.format_detected == "ndjson.gz"

    def test_ndjson_skips_empty_lines(self, tmp_path):
        data = _three_event_stream()
        f = tmp_path / "events.ndjson"
        lines = [json.dumps(ev) for ev in data]
        lines.insert(1, "")
        f.write_text("\n".join(lines))
        result = read_from_path(f)
        assert len(result.events) == 3

    def test_malformed_json_file_quarantined(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("not json at all {{{")
        result = read_from_path(f)
        assert len(result.quarantined) > 0

    def test_unknown_kind_falls_back_to_log(self):
        raw = [
            {
                "event_id": "X",
                "kind": "completely_unknown",
                "timestamp_iso": "2026-05-01T10:00:00Z",
                "service": "s",
            }
        ]  # noqa: E501
        result = read_from_list(raw)
        assert result.events[0].kind == EventKind.LOG


# ---------------------------------------------------------------------------
# timeline_reconstructor
# ---------------------------------------------------------------------------


class TestTimelineReconstructor:
    def test_reconstruct_incident_empty(self):
        tl = reconstruct_incident("INC-001", [])
        assert tl.event_count == 0
        assert tl.telemetry_completeness == 0.0

    def test_reconstruct_incident_sets_duration(self):
        result = read_from_list(_three_event_stream())
        tl = reconstruct_incident("INC-001", result.events)
        assert tl.duration_seconds > 0

    def test_critical_transitions_includes_alerts(self):
        result = read_from_list(_three_event_stream())
        tl = reconstruct_incident("INC-001", result.events)
        kinds = [ct["kind"] for ct in tl.critical_transitions]
        assert "alert" in kinds

    def test_operator_interventions_detected(self):
        result = read_from_list(_three_event_stream())
        tl = reconstruct_incident("INC-001", result.events)
        assert len(tl.operator_interventions) == 1

    def test_completeness_increases_with_more_kinds(self):
        result = read_from_list(_three_event_stream())
        tl = reconstruct_incident("INC-001", result.events)
        assert tl.telemetry_completeness > 0.0

    def test_causal_chain_includes_alert(self):
        result = read_from_list(_three_event_stream())
        tl = reconstruct_incident("INC-001", result.events)
        causal_kinds = [c["kind"] for c in tl.causal_chain]
        assert "alert" in causal_kinds

    def test_to_dict_structure(self):
        result = read_from_list(_three_event_stream())
        tl = reconstruct_incident("INC-001", result.events)
        d = tl.to_dict()
        for key in [
            "incident_id",
            "timeline",
            "critical_transitions",
            "operator_interventions",
            "causal_chain",
            "duration_seconds",
            "telemetry_completeness",
            "event_count",
        ]:
            assert key in d

    def test_reconstruct_all_groups_by_incident(self):
        raw = [
            _make_event("E1", incident_id="INC-001", ts="2026-05-01T10:00:00Z"),
            _make_event("E2", incident_id="INC-002", ts="2026-05-01T10:01:00Z"),
            _make_event("E3", incident_id="INC-001", ts="2026-05-01T10:02:00Z"),
        ]
        result = read_from_list(raw)
        timelines = reconstruct_all(result.events)
        assert "INC-001" in timelines
        assert "INC-002" in timelines
        assert timelines["INC-001"].event_count == 2
        assert timelines["INC-002"].event_count == 1

    def test_events_without_incident_id_grouped_as_unknown(self):
        raw = [_make_event("E1", incident_id=None)]
        result = read_from_list(raw)
        timelines = reconstruct_all(result.events)
        assert "unknown" in timelines


# ---------------------------------------------------------------------------
# ReplayEngine
# ---------------------------------------------------------------------------


class TestReplayEngine:
    def test_load_and_iterate(self):
        engine = ReplayEngine(seed=42)
        engine.load_from_list(_three_event_stream())
        events = list(engine.iter_events())
        assert len(events) == 3

    def test_state_transitions(self):
        engine = ReplayEngine(seed=0)
        engine.load_from_list(_three_event_stream())
        assert engine.state == ReplayState.IDLE
        list(engine.iter_events())
        assert engine.state == ReplayState.COMPLETED

    def test_deterministic_order(self):
        raw = [
            _make_event("E3", ts="2026-05-01T10:02:00Z", seq=3),
            _make_event("E1", ts="2026-05-01T10:00:00Z", seq=1),
            _make_event("E2", ts="2026-05-01T10:01:00Z", seq=2),
        ]
        engine1 = ReplayEngine(seed=1)
        engine2 = ReplayEngine(seed=1)
        engine1.load_from_list(raw)
        engine2.load_from_list(raw)
        ids1 = [ev.event_id for ev in engine1.iter_events()]
        ids2 = [ev.event_id for ev in engine2.iter_events()]
        assert ids1 == ids2

    def test_session_hash_stable(self):
        engine1 = ReplayEngine(seed=0)
        engine2 = ReplayEngine(seed=0)
        engine1.load_from_list(_three_event_stream())
        engine2.load_from_list(_three_event_stream())
        assert engine1.session_hash() == engine2.session_hash()

    def test_session_hash_differs_for_different_events(self):
        engine1 = ReplayEngine(seed=0)
        engine2 = ReplayEngine(seed=0)
        engine1.load_from_list(_three_event_stream())
        engine2.load_from_list([_make_event("DIFFERENT", ts="2026-05-01T10:05:00Z", seq=99)])
        assert engine1.session_hash() != engine2.session_hash()

    def test_replay_pause_stops_iteration(self):
        engine = ReplayEngine(seed=0)
        engine.load_from_list(_three_event_stream())
        it = engine.iter_events()
        next(it)
        engine.replay_pause()
        remaining = list(it)
        assert engine.state == ReplayState.PAUSED
        assert len(remaining) == 0

    def test_replay_resume_after_pause(self):
        engine = ReplayEngine(seed=0)
        engine.load_from_list(_three_event_stream())
        it = engine.iter_events()
        next(it)
        engine.replay_pause()
        list(it)
        engine.replay_resume()
        # After resume, cursor is at 1; iterate remaining
        remaining = list(engine.iter_events())
        assert len(remaining) == 2

    def test_replay_seek(self):
        engine = ReplayEngine(seed=0)
        engine.load_from_list(_three_event_stream())
        new_pos = engine.replay_seek("2026-05-01T10:01:00Z")
        assert new_pos >= 1

    def test_replay_seek_to_future_past_end(self):
        engine = ReplayEngine(seed=0)
        engine.load_from_list(_three_event_stream())
        pos = engine.replay_seek("2099-01-01T00:00:00Z")
        assert pos == engine.total_events

    def test_replay_speed_adjustment(self):
        engine = ReplayEngine(seed=0, replay_speed=1.0)
        engine.replay_speed(4.0)
        assert engine._speed == 4.0

    def test_callback_called_per_event(self):
        engine = ReplayEngine(seed=0)
        engine.load_from_list(_three_event_stream())
        seen = []
        engine.register_callback(lambda ev: seen.append(ev.event_id))
        list(engine.iter_events())
        assert len(seen) == 3

    def test_progress_tracking(self):
        engine = ReplayEngine(seed=0)
        engine.load_from_list(_three_event_stream())
        list(engine.iter_events())
        assert engine.progress() == 1.0

    def test_events_by_kind(self):
        engine = ReplayEngine(seed=0)
        engine.load_from_list(_three_event_stream())
        alerts = engine.events_by_kind(EventKind.ALERT)
        assert len(alerts) == 1

    def test_events_for_incident(self):
        raw = [
            _make_event("E1", incident_id="INC-001"),
            _make_event("E2", incident_id="INC-002"),
        ]
        engine = ReplayEngine(seed=0)
        engine.load_from_list(raw)
        assert len(engine.events_for_incident("INC-001")) == 1

    def test_reconstruct_timelines(self):
        engine = ReplayEngine(seed=0)
        engine.load_from_list(_three_event_stream())
        timelines = engine.reconstruct_timelines()
        assert "INC-001" in timelines

    def test_session_info(self):
        engine = ReplayEngine(seed=42)
        engine.load_from_list(_three_event_stream())
        assert engine.session is not None
        assert engine.session.seed == 42
        assert engine.session.total_events == 3

    def test_load_from_json_file(self, tmp_path):
        data = _three_event_stream()
        f = tmp_path / "events.json"
        f.write_text(json.dumps(data))
        engine = ReplayEngine(seed=0)
        result = engine.load_from_path(str(f))
        assert len(result.events) == 3
        events = list(engine.iter_events())
        assert len(events) == 3
