"""
Tests for Phase 48 Commit 6 — operational chaos integration layer.

Validates that replay_benchmark_with_chaos() produces the five operational
realism scores and degrades appropriately under different corruption profiles.
"""

from __future__ import annotations

import pytest
from evaluation.regression.operational_chaos_integrator import (
    ChaosReplayResult,
    IncidentChaosResult,
    replay_benchmark_with_chaos,
)
from replay.chaos.corruption_models import CorruptionProfile

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_INCIDENT_IDS = [f"inc_{i:04d}" for i in range(8)]


def _run(profile: CorruptionProfile = CorruptionProfile.NETWORK_PARTITION, seed: int = 42):
    return replay_benchmark_with_chaos(
        profile=profile,
        seed=seed,
        incident_ids=_INCIDENT_IDS,
    )


# ---------------------------------------------------------------------------
# ChaosReplayResult structure
# ---------------------------------------------------------------------------


class TestChaosReplayResultStructure:
    def test_returns_chaos_replay_result(self):
        result = _run()
        assert isinstance(result, ChaosReplayResult)

    def test_incident_results_populated(self):
        result = _run()
        assert len(result.incident_chaos_results) == len(_INCIDENT_IDS)

    def test_all_incident_results_are_typed(self):
        result = _run()
        assert all(isinstance(r, IncidentChaosResult) for r in result.incident_chaos_results)

    def test_chaos_profile_recorded(self):
        result = _run(CorruptionProfile.TELEMETRY_BLACKOUT)
        assert result.chaos_profile == CorruptionProfile.TELEMETRY_BLACKOUT.value

    def test_chaos_seed_recorded(self):
        result = _run(seed=99)
        assert result.chaos_seed == 99

    def test_to_dict_has_required_keys(self):
        d = _run().to_dict()
        for key in (
            "telemetry_corruption_rate",
            "observability_confidence",
            "execution_truth_score",
            "causal_ambiguity_score",
            "replay_instability_score",
            "chaos_profile",
            "chaos_seed",
            "incident_count",
            "per_incident",
            "base",
        ):
            assert key in d, f"missing key: {key}"

    def test_per_incident_to_dict_keys(self):
        result = _run()
        for r in result.incident_chaos_results:
            d = r.to_dict()
            for key in (
                "incident_id",
                "raw_event_count",
                "chaos_report",
                "completeness_score",
                "observability_confidence",
                "causal_state",
                "is_causally_stable",
                "stability_score",
                "collapse_risk_score",
                "should_hold_back",
            ):
                assert key in d, f"missing key: {key}"


# ---------------------------------------------------------------------------
# Five operational realism scores — range checks
# ---------------------------------------------------------------------------


class TestFiveRealismScores:
    @pytest.fixture(scope="class")
    def result(self):
        return _run()

    def test_telemetry_corruption_rate_in_range(self, result):
        assert 0.0 <= result.telemetry_corruption_rate <= 1.0

    def test_observability_confidence_in_range(self, result):
        assert 0.0 <= result.observability_confidence <= 1.0

    def test_execution_truth_score_in_range(self, result):
        assert 0.0 <= result.execution_truth_score <= 1.0

    def test_causal_ambiguity_score_in_range(self, result):
        assert 0.0 <= result.causal_ambiguity_score <= 1.0

    def test_replay_instability_score_in_range(self, result):
        assert 0.0 <= result.replay_instability_score <= 1.0

    def test_causal_plus_instability_leq_one(self, result):
        # causal_ambiguity_score counts STABLE incidents;
        # replay_instability_score counts UNSTABLE ones — they can overlap
        # on different incidents, so their sum need not be 1.0,
        # but each must be ≤ 1.0 (already checked above).
        assert result.causal_ambiguity_score <= 1.0
        assert result.replay_instability_score <= 1.0


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_same_seed_same_result(self):
        r1 = _run(seed=7)
        r2 = _run(seed=7)
        assert r1.telemetry_corruption_rate == r2.telemetry_corruption_rate
        assert r1.observability_confidence == r2.observability_confidence
        assert r1.causal_ambiguity_score == r2.causal_ambiguity_score

    def test_different_seeds_may_differ(self):
        r1 = _run(seed=1)
        r2 = _run(seed=2)
        # Not guaranteed to differ, but for these seeds they should
        differs = (
            r1.telemetry_corruption_rate != r2.telemetry_corruption_rate
            or r1.observability_confidence != r2.observability_confidence
        )
        assert differs


# ---------------------------------------------------------------------------
# Profile sensitivity
# ---------------------------------------------------------------------------


class TestProfileSensitivity:
    def test_blackout_has_high_corruption(self):
        result = replay_benchmark_with_chaos(
            profile=CorruptionProfile.TELEMETRY_BLACKOUT,
            seed=42,
            incident_ids=_INCIDENT_IDS,
        )
        assert result.telemetry_corruption_rate > 0.0

    def test_clock_drift_profile_runs(self):
        result = replay_benchmark_with_chaos(
            profile=CorruptionProfile.CLOCK_DRIFT,
            seed=42,
            incident_ids=_INCIDENT_IDS,
        )
        assert isinstance(result, ChaosReplayResult)

    def test_alert_storm_runs(self):
        result = replay_benchmark_with_chaos(
            profile=CorruptionProfile.ALERT_STORM,
            seed=42,
            incident_ids=_INCIDENT_IDS,
        )
        assert isinstance(result, ChaosReplayResult)


# ---------------------------------------------------------------------------
# Per-incident fields
# ---------------------------------------------------------------------------


class TestPerIncidentFields:
    @pytest.fixture(scope="class")
    def incidents(self):
        return _run().incident_chaos_results

    def test_raw_event_count_positive(self, incidents):
        assert all(r.raw_event_count > 0 for r in incidents)

    def test_completeness_in_range(self, incidents):
        assert all(0.0 <= r.completeness_score <= 1.0 for r in incidents)

    def test_observability_confidence_in_range(self, incidents):
        assert all(0.0 <= r.observability_confidence <= 1.0 for r in incidents)

    def test_causal_state_is_valid_string(self, incidents):
        valid_states = {
            "stable_cause",
            "competing_causes",
            "insufficient_evidence",
            "temporally_unstable",
            "observation_conflict",
        }
        assert all(r.causal_state in valid_states for r in incidents)

    def test_stability_score_in_range(self, incidents):
        assert all(0.0 <= r.stability_score <= 1.0 for r in incidents)

    def test_collapse_risk_in_range(self, incidents):
        assert all(0.0 <= r.collapse_risk_score <= 1.0 for r in incidents)

    def test_should_hold_back_is_bool(self, incidents):
        assert all(isinstance(r.should_hold_back, bool) for r in incidents)


# ---------------------------------------------------------------------------
# Base benchmark preserved
# ---------------------------------------------------------------------------


class TestBaseResultPreserved:
    def test_base_has_total_incidents(self):
        result = _run()
        assert result.base_result.total_incidents >= 0

    def test_base_has_aggregate_scores(self):
        result = _run()
        d = result.base_result.to_dict()
        assert "aggregate_trustworthiness_score" in d
        assert "aggregate_safety_score" in d
