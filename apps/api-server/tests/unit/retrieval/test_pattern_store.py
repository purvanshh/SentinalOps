from __future__ import annotations

from agents.rootcause_agent.evidence_weighter import (
    compute_evidence_hash,
    weight_evidence,
)
from retrieval.pattern_store import PatternStore


def test_pattern_store_signatures() -> None:
    store = PatternStore()
    signatures = store.get_signatures()
    assert len(signatures) == 5

    # Check presence of specific signatures
    sig_ids = {sig.signature_id for sig in signatures}
    assert "database_latency" in sig_ids
    assert "memory_pressure" in sig_ids
    assert "deployment_regression" in sig_ids


def test_pattern_store_matching() -> None:
    store = PatternStore()

    # Case 1: database latency matches database latency signature
    evidence = [
        {"item_type": "metric_anomaly", "source": "metrics"},
        {"item_type": "error_signature", "source": "logs"},
    ]
    matches = store.match_evidence(evidence)
    assert len(matches) > 0
    top_sig, top_score = matches[0]
    assert top_sig.signature_id in [
        "database_latency",
        "deployment_regression",
        "memory_pressure",
    ]
    assert top_score > 0.0

    # Case 2: empty evidence matches nothing (scores 0.0 for those with required types)
    empty_evidence = []
    matches = store.match_evidence(empty_evidence)
    for sig, score in matches:
        if sig.required_evidence_types:
            assert score == 0.0


def test_evidence_weighting() -> None:
    evidence = [
        {
            "item_key": "EVID-1",
            "source": "metrics",
            "timestamp": "2026-05-13T12:00:00Z",
            "service": "payment-api",
            "signal": "cpu_high",
            "value": "95%",
            "severity": "critical",
            "confidence": 0.9,
        },
        {
            "item_key": "EVID-2",
            "source": "logs",
            "timestamp": "2026-05-13T11:58:00Z",  # 2 minutes before EVID-1 (within 5 min)
            "service": "payment-api",
            "signal": "oom_kill",
            "value": "OOM",
            "severity": "critical",
            "confidence": 0.8,
        },
        {
            "item_key": "EVID-3",
            "source": "manual",
            "timestamp": "2026-05-13T11:50:00Z",  # 10 minutes before EVID-1 (outside 5 min)
            "service": "payment-api",
            "signal": "restart",
            "value": "manual restart",
            "severity": "warning",
            "confidence": 0.6,
        },
    ]

    weighted = weight_evidence(evidence)
    assert len(weighted) == 3

    # Check metrics item: reliability=1.0, complete=True, recency=1.2
    # (it is max ts, so diff=0 <= 300)
    # expected weight = 1.0 * 1.0 * 1.2 = 1.2
    assert weighted[0]["weight"] == 1.2

    # Check logs item: reliability=0.8, complete=True, recency=1.2 (diff = 120s <= 300)
    # expected weight = 0.8 * 1.0 * 1.2 = 0.96
    assert weighted[1]["weight"] == 0.96

    # Check manual item: reliability=0.5, complete=True, recency=1.0 (diff = 600s > 300)
    # expected weight = 0.5 * 1.0 * 1.0 = 0.5
    assert weighted[2]["weight"] == 0.5


def test_evidence_weighting_incomplete() -> None:
    # Missing optional/required fields (e.g. signal)
    evidence = [
        {
            "item_key": "EVID-1",
            "source": "metrics",
            "timestamp": "2026-05-13T12:00:00Z",
            "service": "payment-api",
            "value": "95%",
            "severity": "critical",
            "confidence": 0.9,
        }
    ]
    weighted = weight_evidence(evidence)
    # reliability=1.0, complete=False (multiplier 0.7), recency=1.2
    # expected weight = 1.0 * 0.7 * 1.2 = 0.84
    assert weighted[0]["weight"] == 0.84


def test_evidence_hash_deterministic() -> None:
    item1 = {"item_key": "1", "value": "A"}
    item2 = {"value": "A", "item_key": "1"}
    assert compute_evidence_hash(item1) == compute_evidence_hash(item2)
