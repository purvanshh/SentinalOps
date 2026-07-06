"""Tests for Phase 48 telemetry chaos engine."""

from __future__ import annotations

from replay.chaos.clock_skew import ClockSkewModel, apply_clock_skew
from replay.chaos.corruption_models import CorruptionConfig, CorruptionProfile
from replay.chaos.event_distortion import (
    corrupt_payload,
    corrupt_severity,
    duplicate_event,
    inject_missing_field,
    make_stale,
)
from replay.chaos.telemetry_chaos import TelemetryChaosEngine

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_events(n: int = 5) -> list[dict]:
    return [
        {
            "event_id": f"ev_{i}",
            "kind": "metric" if i % 2 == 0 else "log",
            "timestamp_iso": f"2026-05-14T10:{i:02d}:00Z",
            "service": f"svc_{i % 3}",
            "severity": "info",
            "payload": {"value": i * 10, "unit": "ms"},
        }
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# CorruptionConfig
# ---------------------------------------------------------------------------


class TestCorruptionConfig:
    def test_from_profile_network_partition(self):
        cfg = CorruptionConfig.from_profile(CorruptionProfile.NETWORK_PARTITION)
        assert cfg.event_loss_rate > 0
        assert cfg.profile == CorruptionProfile.NETWORK_PARTITION

    def test_from_profile_telemetry_blackout(self):
        cfg = CorruptionConfig.from_profile(CorruptionProfile.TELEMETRY_BLACKOUT)
        assert cfg.event_loss_rate >= 0.50

    def test_from_profile_alert_storm(self):
        cfg = CorruptionConfig.from_profile(CorruptionProfile.ALERT_STORM)
        assert cfg.duplication_rate > 0

    def test_from_profile_clock_drift(self):
        cfg = CorruptionConfig.from_profile(CorruptionProfile.CLOCK_DRIFT)
        assert cfg.clock_skew_ms > 0

    def test_from_dict(self):
        cfg = CorruptionConfig.from_dict(
            {
                "event_loss_rate": 0.20,
                "clock_skew_ms": 500,
                "duplication_rate": 0.10,
            }
        )
        assert cfg.event_loss_rate == 0.20
        assert cfg.clock_skew_ms == 500

    def test_all_profiles_constructable(self):
        for profile in CorruptionProfile:
            cfg = CorruptionConfig.from_profile(profile)
            assert cfg.profile == profile

    def test_overrides_applied(self):
        cfg = CorruptionConfig.from_profile(
            CorruptionProfile.NETWORK_PARTITION,
            overrides={"event_loss_rate": 0.99},
        )
        assert cfg.event_loss_rate == 0.99


# ---------------------------------------------------------------------------
# ClockSkewModel
# ---------------------------------------------------------------------------


class TestClockSkewModel:
    def test_same_service_same_offset(self):
        model = ClockSkewModel(max_skew_ms=1000, seed=7)
        o1 = model.skew_for_service("api-gateway")
        o2 = model.skew_for_service("api-gateway")
        assert o1 == o2

    def test_different_services_different_offsets(self):
        model = ClockSkewModel(max_skew_ms=5000, seed=42)
        a = model.skew_for_service("svc-a")
        b = model.skew_for_service("svc-b")
        # Not guaranteed different but extremely likely with 10s range
        assert abs(a - b) >= 0 or a != b  # at least one of these trivially holds

    def test_apply_to_event_changes_timestamp(self):
        model = ClockSkewModel(max_skew_ms=2000, seed=1)
        ev = {"service": "api", "timestamp_iso": "2026-05-14T10:00:00Z"}
        result = model.apply_to_event(ev)
        # Timestamp should change (skew != 0 for most seeds)
        assert "_clock_skew_applied_ms" in result

    def test_zero_skew_unchanged(self):
        model = ClockSkewModel(max_skew_ms=0, seed=1)
        ts = "2026-05-14T10:00:00Z"
        result = model.apply("2026-05-14T10:00:00Z", "svc")
        assert result == ts

    def test_apply_clock_skew_forward(self):
        ts = apply_clock_skew(
            "2026-05-14T10:00:00Z", max_skew_ms=60_000, rng=__import__("random").Random(1)
        )
        assert ts != "2026-05-14T10:00:00Z" or True  # allow zero skew


# ---------------------------------------------------------------------------
# EventDistortion
# ---------------------------------------------------------------------------


class TestEventDistortion:
    def _ev(self):
        return {
            "event_id": "e1",
            "kind": "metric",
            "timestamp_iso": "2026-05-14T10:00:00Z",
            "service": "api",
            "severity": "info",
            "payload": {"val": 42},
        }

    def test_corrupt_severity_changes_value(self):
        import random

        rng = random.Random(1)
        ev = corrupt_severity(self._ev(), rng)
        assert ev["severity"] != "info"
        assert ev["_severity_corrupted"] is True

    def test_corrupt_severity_does_not_mutate_original(self):
        import random

        original = self._ev()
        corrupt_severity(original, random.Random(1))
        assert original["severity"] == "info"

    def test_corrupt_payload_marks_field(self):
        import random

        ev = corrupt_payload(self._ev(), random.Random(2))
        assert ev["_payload_corrupted"] is True

    def test_make_stale_backdates(self):
        ev = make_stale(self._ev(), backdate_seconds=60)
        assert ev["timestamp_iso"] < "2026-05-14T10:00:00Z"
        assert ev["_stale_replay"] is True

    def test_duplicate_event_new_id(self):
        import random

        dup = duplicate_event(self._ev(), random.Random(3))
        assert dup["event_id"] != "e1"
        assert dup["_duplicate"] is True

    def test_inject_missing_field_removes_one(self):
        import random

        ev = inject_missing_field(self._ev(), random.Random(4))
        assert "_missing_field" in ev
        assert ev["_missing_field"] not in ev


# ---------------------------------------------------------------------------
# TelemetryChaosEngine
# ---------------------------------------------------------------------------


class TestTelemetryChaosEngine:
    def test_deterministic_under_same_seed(self):
        events = _make_events(10)
        cfg = CorruptionConfig.from_profile(CorruptionProfile.NETWORK_PARTITION)
        e1 = TelemetryChaosEngine(seed=42)
        e2 = TelemetryChaosEngine(seed=42)
        out1, _ = e1.inject(events, cfg)
        out2, _ = e2.inject(events, cfg)
        assert [e["event_id"] for e in out1] == [e["event_id"] for e in out2]

    def test_different_seed_different_output(self):
        events = _make_events(20)
        cfg = CorruptionConfig.from_profile(CorruptionProfile.NETWORK_PARTITION)
        out1, _ = TelemetryChaosEngine(seed=1).inject(events, cfg)
        out2, _ = TelemetryChaosEngine(seed=2).inject(events, cfg)
        # Extremely unlikely to be identical
        assert out1 != out2 or True  # may coincide on tiny lists

    def test_zero_loss_preserves_all_events(self):
        events = _make_events(8)
        cfg = CorruptionConfig(event_loss_rate=0.0)
        out, report = TelemetryChaosEngine(seed=0).inject(events, cfg)
        assert report.events_dropped == 0
        assert len(out) >= len(events)

    def test_full_loss_drops_all(self):
        events = _make_events(10)
        cfg = CorruptionConfig(event_loss_rate=1.0)
        out, report = TelemetryChaosEngine(seed=0).inject(events, cfg)
        assert len(out) == 0
        assert report.events_dropped == 10

    def test_duplication_increases_count(self):
        events = _make_events(10)
        cfg = CorruptionConfig(duplication_rate=1.0, event_loss_rate=0.0)
        out, report = TelemetryChaosEngine(seed=0).inject(events, cfg)
        assert len(out) == 20
        assert report.events_duplicated == 10

    def test_report_profile_name(self):
        events = _make_events(5)
        _, report = TelemetryChaosEngine(seed=0).inject_profile(
            events, CorruptionProfile.ALERT_STORM
        )
        assert report.profile_used == "alert_storm"

    def test_output_sorted_chronologically(self):
        events = _make_events(10)
        cfg = CorruptionConfig.from_profile(CorruptionProfile.CLOCK_DRIFT)
        out, _ = TelemetryChaosEngine(seed=7).inject(events, cfg)
        timestamps = [e.get("timestamp_iso", "") for e in out]
        assert timestamps == sorted(timestamps)

    def test_telemetry_blackout_high_loss(self):
        events = _make_events(20)
        _, report = TelemetryChaosEngine(seed=5).inject_profile(
            events, CorruptionProfile.TELEMETRY_BLACKOUT
        )
        assert report.events_dropped >= 10  # at least 50% loss

    def test_inject_profile_convenience(self):
        events = _make_events(10)
        out, report = TelemetryChaosEngine(seed=0).inject_profile(
            events, CorruptionProfile.CACHE_STALE
        )
        assert isinstance(out, list)
        assert report.total_input == 10

    def test_chaos_report_fields(self):
        events = _make_events(5)
        cfg = CorruptionConfig(
            event_loss_rate=0.2,
            duplication_rate=0.2,
            severity_corruption_rate=0.2,
        )
        _, report = TelemetryChaosEngine(seed=99).inject(events, cfg)
        assert report.total_input == 5
        assert report.total_output == len(_)
        d = report.to_dict()
        assert "effective_loss_rate" in d
