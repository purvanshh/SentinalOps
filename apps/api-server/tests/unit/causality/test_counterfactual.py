"""
Phase 43 counterfactual reasoning and causal confidence tests.

Proves:
  - test_temporal_necessity: passes when cause precedes effect.
  - test_temporal_necessity: fails when cause comes after effect.
  - test_topology_necessity: passes for same-service and valid dep path.
  - test_topology_necessity: fails when no topology path exists.
  - test_redundancy: fails when a stronger alternative exists.
  - evaluate_counterfactual: deployment after anomaly fails counterfactual.
  - evaluate_counterfactual: upstream DB failure before API anomaly passes.
  - compute_causal_confidence: penalizes contradictory evidence.
  - compute_causal_confidence: rewards strong temporal and topology alignment.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from causality.counterfactual import (
    check_redundancy,
    check_temporal_necessity,
    check_topology_necessity,
    compute_causal_confidence,
    evaluate_counterfactual,
)


def _ts(offset_seconds: float = 0.0) -> str:
    base = datetime(2024, 1, 1, 14, 0, 0, tzinfo=UTC)
    return (base + timedelta(seconds=offset_seconds)).isoformat()


# ─── test_temporal_necessity ──────────────────────────────────────────────────


def test_check_temporal_necessity_passes_when_cause_before_effect() -> None:
    ok, reason = check_temporal_necessity(_ts(0), _ts(300))
    assert ok is True
    assert "preceded" in reason


def test_check_temporal_necessity_fails_when_cause_after_effect() -> None:
    ok, reason = check_temporal_necessity(_ts(300), _ts(0))
    assert ok is False
    assert "AFTER" in reason


def test_check_temporal_necessity_passes_for_simultaneous() -> None:
    ts = _ts(0)
    ok, _ = check_temporal_necessity(ts, ts)
    assert ok is True


# ─── test_topology_necessity ──────────────────────────────────────────────────


def test_check_topology_necessity_passes_same_service() -> None:
    ok, reason = check_topology_necessity("payment-api", "payment-api", {})
    assert ok is True
    assert "same service" in reason


def test_check_topology_necessity_passes_direct_dependency() -> None:
    topology = {"dependencies": {"database": ["payment-api"]}}
    ok, reason = check_topology_necessity("database", "payment-api", topology)
    assert ok is True
    assert "dependency path" in reason


def test_check_topology_necessity_passes_transitive_dependency() -> None:
    topology = {
        "dependencies": {
            "database": ["payment-api"],
            "payment-api": ["checkout"],
        }
    }
    ok, _ = check_topology_necessity("database", "checkout", topology)
    assert ok is True


def test_check_topology_necessity_fails_no_path() -> None:
    topology = {"dependencies": {"database": ["payment-api"]}}
    ok, reason = check_topology_necessity("database", "unrelated-service", topology)
    assert ok is False
    assert "impossible" in reason


def test_check_topology_necessity_passes_empty_topology() -> None:
    ok, _ = check_topology_necessity("db", "api", {})
    assert ok is True


# ─── test_redundancy ─────────────────────────────────────────────────────────


def test_check_redundancy_passes_no_alternatives() -> None:
    ok, _ = check_redundancy("cand-1", [])
    assert ok is True


def test_check_redundancy_fails_when_stronger_alternative_exists() -> None:
    alternatives = [{"id": "cand-2", "confidence": 0.95, "description": "primary cause"}]
    ok, reason = check_redundancy("cand-1", alternatives)
    assert ok is False
    assert "primary cause" in reason


def test_check_redundancy_passes_when_no_alternative_above_threshold() -> None:
    alternatives = [{"id": "cand-2", "confidence": 0.50, "description": "weak candidate"}]
    ok, _ = check_redundancy("cand-1", alternatives)
    assert ok is True


# ─── evaluate_counterfactual ──────────────────────────────────────────────────


def test_counterfactual_deployment_after_anomaly_fails() -> None:
    candidate = {
        "id": "deploy-1",
        "description": "deployment to payment-api",
        "timestamp_iso": _ts(300),
        "service": "payment-api",
    }
    result = evaluate_counterfactual(
        candidate,
        effect_timestamp=_ts(0),
        effect_service="payment-api",
    )
    assert result.passes_counterfactual is False
    assert result.temporal_necessity is False


def test_counterfactual_upstream_db_failure_passes() -> None:
    topology = {"dependencies": {"database": ["payment-api"]}}
    candidate = {
        "id": "db-failure",
        "description": "postgres connection pool exhausted",
        "timestamp_iso": _ts(0),
        "service": "database",
    }
    result = evaluate_counterfactual(
        candidate,
        effect_timestamp=_ts(120),
        effect_service="payment-api",
        topology=topology,
    )
    assert result.passes_counterfactual is True
    assert result.temporal_necessity is True
    assert result.topology_necessity is True


def test_counterfactual_impossible_topology_fails() -> None:
    topology = {"dependencies": {"database": ["payment-api"]}}
    candidate = {
        "id": "cand",
        "description": "unrelated service failure",
        "timestamp_iso": _ts(0),
        "service": "unrelated-service",
    }
    result = evaluate_counterfactual(
        candidate,
        effect_timestamp=_ts(120),
        effect_service="payment-api",
        topology=topology,
    )
    assert result.topology_necessity is False
    assert result.passes_counterfactual is False


def test_counterfactual_confidence_adjustment_negative_on_failure() -> None:
    candidate = {
        "id": "late-deploy",
        "description": "late deployment",
        "timestamp_iso": _ts(500),
        "service": "payment-api",
    }
    result = evaluate_counterfactual(
        candidate,
        effect_timestamp=_ts(0),
        effect_service="payment-api",
    )
    assert result.confidence_adjustment < 0


def test_counterfactual_explanation_is_non_empty() -> None:
    candidate = {
        "id": "db",
        "description": "db failure",
        "timestamp_iso": _ts(0),
        "service": "database",
    }
    result = evaluate_counterfactual(
        candidate,
        effect_timestamp=_ts(120),
        effect_service="payment-api",
    )
    assert len(result.explanation) > 0


# ─── compute_causal_confidence ────────────────────────────────────────────────


def test_causal_confidence_high_alignment_gives_high_score() -> None:
    candidate = {"id": "db", "pattern_match_score": 0.9}
    score = compute_causal_confidence(
        candidate,
        temporal_alignment=1.0,
        topology_consistency=1.0,
        historical_similarity=0.9,
        contradictory_evidence_count=0,
    )
    assert score.final_confidence > 0.80


def test_causal_confidence_contradictory_evidence_reduces_score() -> None:
    candidate = {"id": "db", "pattern_match_score": 0.8}
    score_clean = compute_causal_confidence(candidate, contradictory_evidence_count=0)
    score_dirty = compute_causal_confidence(candidate, contradictory_evidence_count=5)
    assert score_dirty.final_confidence < score_clean.final_confidence


def test_causal_confidence_never_exceeds_one() -> None:
    candidate = {"id": "db", "pattern_match_score": 1.0}
    score = compute_causal_confidence(
        candidate,
        temporal_alignment=1.0,
        topology_consistency=1.0,
        historical_similarity=1.0,
    )
    assert score.final_confidence <= 1.0


def test_causal_confidence_never_below_zero() -> None:
    candidate = {"id": "db", "pattern_match_score": 0.0}
    score = compute_causal_confidence(
        candidate,
        temporal_alignment=0.0,
        topology_consistency=0.0,
        historical_similarity=0.0,
        contradictory_evidence_count=10,
    )
    assert score.final_confidence >= 0.0


def test_causal_confidence_factors_list_mentions_issues() -> None:
    candidate = {"id": "db", "pattern_match_score": 0.5}
    score = compute_causal_confidence(
        candidate,
        temporal_alignment=0.2,
        topology_consistency=0.3,
        contradictory_evidence_count=3,
    )
    factors_text = " ".join(score.factors)
    assert (
        "temporal" in factors_text or "topology" in factors_text or "contradictory" in factors_text
    )
