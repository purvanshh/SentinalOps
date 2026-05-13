"""Tests for Phase 48 causal ambiguity and uncertainty collapse prevention."""

from __future__ import annotations

from causality.reality.ambiguity_resolver import AmbiguityResolver, CausalRealityState
from causality.reality.causal_stability import CausalStabilityAnalyzer
from causality.reality.contradiction_graph import ContradictionGraph
from causality.reality.uncertainty_collapse import UncertaintyCollapseGuard

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hyp(mechanism: str, conf: float, evidence: list[str] | None = None) -> dict:
    return {
        "mechanism": mechanism,
        "confidence": conf,
        "supporting_evidence": evidence or [f"ev_{mechanism[:8]}_{i}" for i in range(2)],
    }


# ---------------------------------------------------------------------------
# AmbiguityResolver
# ---------------------------------------------------------------------------


class TestAmbiguityResolver:
    def test_stable_cause_high_conf_single(self):
        r = AmbiguityResolver()
        report = r.resolve([_hyp("db_pool_exhaustion", 0.85)])
        assert report.state == CausalRealityState.STABLE_CAUSE

    def test_competing_causes_small_gap(self):
        r = AmbiguityResolver()
        report = r.resolve([_hyp("cpu_saturation", 0.55), _hyp("memory_leak", 0.52)])
        assert report.state == CausalRealityState.COMPETING_CAUSES

    def test_insufficient_evidence_no_hypotheses(self):
        r = AmbiguityResolver()
        report = r.resolve([])
        assert report.state == CausalRealityState.INSUFFICIENT_EVIDENCE

    def test_insufficient_evidence_low_confidence(self):
        r = AmbiguityResolver()
        report = r.resolve([_hyp("network_partition", 0.10, [])])
        assert report.state == CausalRealityState.INSUFFICIENT_EVIDENCE

    def test_observation_conflict_overrides_all(self):
        r = AmbiguityResolver()
        report = r.resolve(
            [_hyp("db_pool_exhaustion", 0.90)],
            has_observation_conflict=True,
        )
        assert report.state == CausalRealityState.OBSERVATION_CONFLICT
        assert report.should_refuse_attribution

    def test_temporal_instability_state(self):
        r = AmbiguityResolver()
        report = r.resolve(
            [_hyp("deploy_config_change", 0.75)],
            has_temporal_instability=True,
        )
        assert report.state == CausalRealityState.TEMPORALLY_UNSTABLE

    def test_confidence_cap_applied(self):
        r = AmbiguityResolver()
        report = r.resolve([_hyp("cpu_saturation", 0.55), _hyp("memory_leak", 0.52)])
        assert report.confidence_cap <= 0.65

    def test_stable_is_true_for_stable_cause(self):
        r = AmbiguityResolver()
        report = r.resolve([_hyp("db_pool_exhaustion", 0.85)])
        assert report.is_stable

    def test_to_dict(self):
        r = AmbiguityResolver()
        d = r.resolve([_hyp("db_pool_exhaustion", 0.75)]).to_dict()
        assert "state" in d and "confidence_cap" in d


# ---------------------------------------------------------------------------
# ContradictionGraph
# ---------------------------------------------------------------------------


class TestContradictionGraph:
    def test_add_contradiction(self):
        g = ContradictionGraph()
        g.add_contradiction("cpu_saturation", "memory_leak", "different resources", "high")
        report = g.analyze()
        assert report.contradiction_count == 1

    def test_irreconcilable_on_high_severity(self):
        g = ContradictionGraph()
        g.add_contradiction("cpu", "db", "irreconcilable", "high")
        report = g.analyze()
        assert report.has_irreconcilable

    def test_no_irreconcilable_on_low_severity(self):
        g = ContradictionGraph()
        g.add_contradiction("cpu", "db", "minor discrepancy", "low")
        report = g.analyze()
        assert not report.has_irreconcilable

    def test_most_contradicted_identified(self):
        g = ContradictionGraph()
        g.add_contradiction("cpu", "db", "r1", "medium")
        g.add_contradiction("cpu", "net", "r2", "medium")
        report = g.analyze()
        assert report.most_contradicted == "cpu"

    def test_add_from_hypotheses_detects_cross_category(self):
        g = ContradictionGraph()
        hyps = [_hyp("db_connection_pool", 0.50), _hyp("network_partition", 0.50)]
        g.add_from_hypotheses(hyps)
        report = g.analyze()
        assert report.contradiction_count >= 1

    def test_clear_resets_state(self):
        g = ContradictionGraph()
        g.add_contradiction("cpu", "db", "r", "high")
        g.clear()
        assert g.analyze().contradiction_count == 0

    def test_to_dict(self):
        g = ContradictionGraph()
        g.add_contradiction("cpu", "db", "r", "medium")
        d = g.analyze().to_dict()
        assert "contradiction_count" in d


# ---------------------------------------------------------------------------
# UncertaintyCollapseGuard
# ---------------------------------------------------------------------------


class TestUncertaintyCollapseGuard:
    def test_safe_attribution_no_risks(self):
        guard = UncertaintyCollapseGuard()
        report = guard.check(
            proposed_confidence=0.85,
            evidence_count=5,
            hypothesis_count=3,
            top_gap=0.30,
            telemetry_completeness=0.90,
        )
        assert len(report.risks) == 0
        assert not report.should_hold_back_attribution

    def test_high_confidence_sparse_evidence_risk(self):
        guard = UncertaintyCollapseGuard()
        report = guard.check(
            proposed_confidence=0.85,
            evidence_count=1,
            hypothesis_count=1,
            top_gap=0.50,
            telemetry_completeness=0.80,
        )
        codes = [r.risk_code for r in report.risks]
        assert "overconfident_sparse_evidence" in codes

    def test_competing_hypotheses_unresolved_risk(self):
        guard = UncertaintyCollapseGuard()
        report = guard.check(
            proposed_confidence=0.60,
            evidence_count=5,
            hypothesis_count=3,
            top_gap=0.05,
            telemetry_completeness=0.80,
        )
        codes = [r.risk_code for r in report.risks]
        assert "competing_hypotheses_unresolved" in codes

    def test_poor_telemetry_attribution_risk(self):
        guard = UncertaintyCollapseGuard()
        report = guard.check(
            proposed_confidence=0.75,
            evidence_count=4,
            hypothesis_count=2,
            top_gap=0.30,
            telemetry_completeness=0.30,
        )
        codes = [r.risk_code for r in report.risks]
        assert "attribution_with_poor_telemetry" in codes

    def test_hold_back_when_risk_high(self):
        guard = UncertaintyCollapseGuard()
        report = guard.check(
            proposed_confidence=0.90,
            evidence_count=1,
            hypothesis_count=1,
            top_gap=0.05,
            telemetry_completeness=0.20,
        )
        assert report.should_hold_back_attribution
        assert report.recommended_max_confidence < 0.90

    def test_to_dict(self):
        guard = UncertaintyCollapseGuard()
        d = guard.check(0.80, 3, 2, 0.25, 0.70).to_dict()
        assert "collapse_risk_score" in d


# ---------------------------------------------------------------------------
# CausalStabilityAnalyzer
# ---------------------------------------------------------------------------


class TestCausalStabilityAnalyzer:
    def test_stable_with_large_gap(self):
        ana = CausalStabilityAnalyzer()
        hyps = [_hyp("db_pool", 0.85, ["ev1", "ev2", "ev3"]), _hyp("memory", 0.40)]
        report = ana.analyze(hyps)
        assert report.is_stable

    def test_unstable_with_small_gap(self):
        ana = CausalStabilityAnalyzer()
        hyps = [_hyp("db_pool", 0.55, ["ev1"]), _hyp("memory", 0.53, ["ev2"])]
        report = ana.analyze(hyps)
        assert not report.is_stable

    def test_single_hypothesis_trivially_stable(self):
        ana = CausalStabilityAnalyzer()
        report = ana.analyze([_hyp("db_pool", 0.80)])
        assert report.is_stable
        assert report.stability_score == 1.0

    def test_empty_hypotheses_not_stable(self):
        ana = CausalStabilityAnalyzer()
        report = ana.analyze([])
        assert not report.is_stable

    def test_stability_score_in_range(self):
        ana = CausalStabilityAnalyzer()
        hyps = [_hyp("db_pool", 0.70, ["ev1", "ev2"]), _hyp("memory", 0.55)]
        report = ana.analyze(hyps)
        assert 0.0 <= report.stability_score <= 1.0

    def test_to_dict(self):
        ana = CausalStabilityAnalyzer()
        d = ana.analyze([_hyp("db_pool", 0.80)]).to_dict()
        assert "is_stable" in d and "stability_score" in d
