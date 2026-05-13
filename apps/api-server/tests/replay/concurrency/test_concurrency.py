"""Tests for Phase 48 concurrent incident and deployment noise modules."""

from __future__ import annotations

from replay.concurrency.concurrent_incidents import ConcurrentIncidentSimulator
from replay.concurrency.deployment_noise import NoiseDeploymentInjector, NoiseDeploymentKind
from replay.concurrency.overlap_resolution import OverlapResolver
from replay.concurrency.signal_disambiguation import SignalClass, SignalDisambiguator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _events(incident_id: str, start_min: int, n: int = 3) -> list[dict]:
    return [
        {
            "event_id": f"{incident_id}_ev{i}",
            "kind": "alert" if i == 0 else "log",
            "timestamp_iso": f"2026-05-14T10:{(start_min + i):02d}:00Z",
            "service": f"svc-{incident_id}",
            "severity": "error",
            "incident_id": incident_id,
            "payload": {"msg": f"{incident_id} event {i}"},
        }
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# ConcurrentIncidentSimulator
# ---------------------------------------------------------------------------


class TestConcurrentIncidentSimulator:
    def test_merge_two_incidents(self):
        sim = ConcurrentIncidentSimulator()
        sim.add_incident("INC-A", _events("INC-A", start_min=0))
        sim.add_incident("INC-B", _events("INC-B", start_min=2))
        result = sim.simulate()
        assert result.incident_count == 2
        assert result.total_events == 6

    def test_merged_events_sorted(self):
        sim = ConcurrentIncidentSimulator()
        sim.add_incident("INC-A", _events("INC-A", start_min=5))
        sim.add_incident("INC-B", _events("INC-B", start_min=0))
        result = sim.simulate()
        timestamps = [e["timestamp_iso"] for e in result.merged_events]
        assert timestamps == sorted(timestamps)

    def test_incident_ids_preserved(self):
        sim = ConcurrentIncidentSimulator()
        sim.add_incident("INC-X", _events("INC-X", start_min=0))
        sim.add_incident("INC-Y", _events("INC-Y", start_min=1))
        result = sim.simulate()
        ids_in_events = {e["incident_id"] for e in result.merged_events}
        assert "INC-X" in ids_in_events
        assert "INC-Y" in ids_in_events

    def test_overlapping_incidents_detected(self):
        sim = ConcurrentIncidentSimulator()
        sim.add_incident("INC-A", _events("INC-A", start_min=0, n=5))
        sim.add_incident("INC-B", _events("INC-B", start_min=2, n=5))
        result = sim.simulate()
        assert result.has_overlap

    def test_non_overlapping_incidents(self):
        sim = ConcurrentIncidentSimulator()
        sim.add_incident("INC-A", _events("INC-A", start_min=0, n=3))
        sim.add_incident("INC-B", _events("INC-B", start_min=30, n=3))
        result = sim.simulate()
        # no overlap (gap of 27 minutes)
        assert not result.has_overlap

    def test_single_incident_no_overlap(self):
        sim = ConcurrentIncidentSimulator()
        sim.add_incident("INC-A", _events("INC-A", start_min=0))
        result = sim.simulate()
        assert not result.has_overlap

    def test_clear_resets_state(self):
        sim = ConcurrentIncidentSimulator()
        sim.add_incident("INC-A", _events("INC-A", start_min=0))
        sim.clear()
        result = sim.simulate()
        assert result.incident_count == 0


# ---------------------------------------------------------------------------
# NoiseDeploymentInjector
# ---------------------------------------------------------------------------


class TestNoiseDeploymentInjector:
    def _base_events(self) -> list[dict]:
        return [
            {
                "event_id": f"e{i}",
                "kind": "metric",
                "timestamp_iso": f"2026-05-14T10:{i:02d}:00Z",
                "service": "api",
                "severity": "error",
                "payload": {},
            }
            for i in range(5)
        ]

    def test_inject_adds_noise_events(self):
        inj = NoiseDeploymentInjector(seed=0)
        result = inj.inject(self._base_events(), noise_count=3)
        assert len(result) == 8

    def test_noise_events_marked(self):
        inj = NoiseDeploymentInjector(seed=1)
        result = inj.inject(self._base_events(), noise_count=2)
        noise = [e for e in result if e.get("_noise_deployment")]
        assert len(noise) == 2

    def test_output_sorted(self):
        inj = NoiseDeploymentInjector(seed=2)
        result = inj.inject(self._base_events(), noise_count=5)
        timestamps = [e["timestamp_iso"] for e in result]
        assert timestamps == sorted(timestamps)

    def test_specific_kind_injection(self):
        inj = NoiseDeploymentInjector(seed=3)
        result = inj.inject(
            self._base_events(),
            noise_count=2,
            kinds=[NoiseDeploymentKind.HARMLESS_DURING_OUTAGE],
        )
        for e in result:
            if e.get("_noise_deployment"):
                assert e["_noise_kind"] == "harmless_during_outage"

    def test_deterministic_under_same_seed(self):
        base = self._base_events()
        r1 = NoiseDeploymentInjector(seed=42).inject(base, noise_count=3)
        r2 = NoiseDeploymentInjector(seed=42).inject(base, noise_count=3)
        assert [e["event_id"] for e in r1] == [e["event_id"] for e in r2]

    def test_empty_events_returns_empty(self):
        inj = NoiseDeploymentInjector(seed=0)
        assert inj.inject([], noise_count=3) == []


# ---------------------------------------------------------------------------
# OverlapResolver
# ---------------------------------------------------------------------------


class TestOverlapResolver:
    def test_resolve_two_incidents(self):
        events_a = _events("INC-A", start_min=0, n=3)
        events_b = _events("INC-B", start_min=2, n=3)
        all_events = events_a + events_b
        resolver = OverlapResolver()
        result = resolver.resolve(all_events, ["INC-A", "INC-B"])
        assert len(result.streams) == 2

    def test_events_assigned_by_incident_id(self):
        events_a = _events("INC-A", start_min=0, n=4)
        events_b = _events("INC-B", start_min=0, n=4)
        resolver = OverlapResolver()
        result = resolver.resolve(events_a + events_b, ["INC-A", "INC-B"])
        stream_a = next(s for s in result.streams if s.incident_id == "INC-A")
        assert len(stream_a.owned_events) + len(stream_a.overlap_events) == 4

    def test_noise_events_in_noise_bucket(self):
        events = _events("INC-A", start_min=0, n=3)
        noise = {
            "event_id": "n1",
            "_noise_deployment": True,
            "timestamp_iso": "2026-05-14T10:01:00Z",
        }
        resolver = OverlapResolver()
        result = resolver.resolve(events + [noise], ["INC-A"])
        stream = result.streams[0]
        assert any(e["event_id"] == "n1" for e in stream.noise_events)

    def test_unknown_incident_goes_to_ambiguous(self):
        events = _events("INC-A", start_min=0, n=3)
        unknown = {
            "event_id": "unknown1",
            "incident_id": "INC-UNKNOWN",
            "timestamp_iso": "2026-05-14T10:00:00Z",
        }
        resolver = OverlapResolver()
        result = resolver.resolve(events + [unknown], ["INC-A"])
        assert any(e["event_id"] == "unknown1" for e in result.ambiguous_events)


# ---------------------------------------------------------------------------
# SignalDisambiguator
# ---------------------------------------------------------------------------


class TestSignalDisambiguator:
    def _ev(self, kind: str, severity: str = "error", noise: bool = False) -> dict:
        return {
            "event_id": f"ev_{kind}_{severity}",
            "kind": kind,
            "severity": severity,
            "_noise_deployment": noise,
            "incident_id": "INC-A",
        }

    def test_noise_marker_classified_as_noise(self):
        d = SignalDisambiguator()
        result = d.disambiguate([self._ev("deployment", noise=True)])
        assert len(result.noise) == 1
        assert result.noise[0].signal_class == SignalClass.NOISE

    def test_deployment_without_noise_is_correlated(self):
        d = SignalDisambiguator()
        result = d.disambiguate([self._ev("deployment")])
        assert len(result.correlated) == 1

    def test_alert_is_causal(self):
        d = SignalDisambiguator()
        result = d.disambiguate([self._ev("alert")])
        assert len(result.causal) == 1

    def test_topology_change_is_causal(self):
        d = SignalDisambiguator()
        result = d.disambiguate([self._ev("topology_change")])
        assert len(result.causal) == 1

    def test_metric_with_error_is_correlated(self):
        d = SignalDisambiguator()
        result = d.disambiguate([self._ev("metric", "error")])
        assert len(result.correlated) == 1

    def test_metric_with_info_is_noise(self):
        d = SignalDisambiguator()
        result = d.disambiguate([self._ev("metric", "info")])
        assert len(result.noise) == 1

    def test_clarity_score_zero_no_causal(self):
        d = SignalDisambiguator()
        events = [self._ev("metric", "info"), self._ev("deployment")]
        result = d.disambiguate(events)
        assert result.causal_clarity_score == 0.0

    def test_clarity_increases_with_causal_signals(self):
        d = SignalDisambiguator()
        events = [self._ev("alert"), self._ev("topology_change"), self._ev("metric", "info")]
        result = d.disambiguate(events)
        assert result.causal_clarity_score > 0.0

    def test_to_dict(self):
        d = SignalDisambiguator()
        result = d.disambiguate([self._ev("alert"), self._ev("metric", "info")])
        out = result.to_dict()
        assert "causal_clarity_score" in out
        assert out["total_signals"] == 2
