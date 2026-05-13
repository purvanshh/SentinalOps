"""
Phase 43 causal event graph and temporal sequencing tests.

Proves:
  - CausalEventGraph stores nodes and edges correctly.
  - Edges must reference existing nodes (ValueError otherwise).
  - predecessors() and successors() return correct neighbors.
  - causal_ancestors() performs BFS over upstream causal chain.
  - build_temporal_edges() adds TEMPORAL_PRECEDES edges within window.
  - detect_temporal_contradictions() flags deployments after anomaly onset.
  - sequence_events_by_time() orders events chronologically.
  - compute_propagation_lag() returns non-negative lag in seconds.
  - to_dict() produces serializable graph representation.
"""
from __future__ import annotations

import pytest
from datetime import UTC, datetime, timedelta

from causality.event_graph import (
    CausalEdge,
    CausalEventGraph,
    CausalNode,
    EdgeType,
    NodeType,
)
from causality.temporal_engine import (
    build_temporal_edges,
    compute_propagation_lag,
    detect_temporal_contradictions,
    sequence_events_by_time,
)


def _ts(offset_seconds: float = 0.0) -> str:
    base = datetime(2024, 1, 1, 14, 0, 0, tzinfo=UTC)
    return (base + timedelta(seconds=offset_seconds)).isoformat()


def _make_node(
    node_id: str,
    node_type: NodeType = NodeType.METRIC_ANOMALY,
    service: str = "payment-api",
    ts_offset: float = 0.0,
) -> CausalNode:
    return CausalNode(
        node_id=node_id,
        node_type=node_type,
        service=service,
        timestamp_iso=_ts(ts_offset),
        description=f"test node {node_id}",
    )


# ─── CausalEventGraph basic operations ───────────────────────────────────────


def test_graph_add_and_retrieve_node() -> None:
    graph = CausalEventGraph()
    node = _make_node("N1")
    graph.add_node(node)
    assert graph.get_node("N1") == node


def test_graph_nodes_returns_all_added_nodes() -> None:
    graph = CausalEventGraph()
    graph.add_node(_make_node("A"))
    graph.add_node(_make_node("B"))
    assert len(graph.nodes) == 2


def test_graph_add_edge_valid() -> None:
    graph = CausalEventGraph()
    graph.add_node(_make_node("A"))
    graph.add_node(_make_node("B"))
    edge = CausalEdge("A", "B", EdgeType.CAUSAL_INFLUENCE)
    graph.add_edge(edge)
    assert len(graph.edges) == 1


def test_graph_add_edge_unknown_source_raises() -> None:
    graph = CausalEventGraph()
    graph.add_node(_make_node("B"))
    with pytest.raises(ValueError, match="unknown node"):
        graph.add_edge(CausalEdge("UNKNOWN", "B", EdgeType.CAUSAL_INFLUENCE))


def test_graph_add_edge_unknown_target_raises() -> None:
    graph = CausalEventGraph()
    graph.add_node(_make_node("A"))
    with pytest.raises(ValueError, match="unknown node"):
        graph.add_edge(CausalEdge("A", "UNKNOWN", EdgeType.CAUSAL_INFLUENCE))


def test_graph_predecessors_returns_upstream_nodes() -> None:
    graph = CausalEventGraph()
    graph.add_node(_make_node("DB"))
    graph.add_node(_make_node("API"))
    graph.add_edge(CausalEdge("DB", "API", EdgeType.CAUSAL_INFLUENCE))
    preds = graph.predecessors("API")
    assert any(n.node_id == "DB" for n in preds)


def test_graph_successors_returns_downstream_nodes() -> None:
    graph = CausalEventGraph()
    graph.add_node(_make_node("DB"))
    graph.add_node(_make_node("API"))
    graph.add_edge(CausalEdge("DB", "API", EdgeType.CAUSAL_INFLUENCE))
    succs = graph.successors("DB")
    assert any(n.node_id == "API" for n in succs)


def test_graph_causal_ancestors_bfs_traversal() -> None:
    graph = CausalEventGraph()
    graph.add_node(_make_node("ROOT"))
    graph.add_node(_make_node("MID"))
    graph.add_node(_make_node("LEAF"))
    graph.add_edge(CausalEdge("ROOT", "MID", EdgeType.CAUSAL_INFLUENCE))
    graph.add_edge(CausalEdge("MID", "LEAF", EdgeType.CAUSAL_INFLUENCE))
    ancestors = graph.causal_ancestors("LEAF")
    ancestor_ids = {n.node_id for n in ancestors}
    assert "MID" in ancestor_ids
    assert "ROOT" in ancestor_ids


def test_graph_to_dict_is_serializable() -> None:
    graph = CausalEventGraph()
    graph.add_node(_make_node("A"))
    graph.add_node(_make_node("B"))
    graph.add_edge(CausalEdge("A", "B", EdgeType.TEMPORAL_PRECEDES))
    d = graph.to_dict()
    assert "nodes" in d
    assert "edges" in d
    assert len(d["nodes"]) == 2
    assert len(d["edges"]) == 1


# ─── build_temporal_edges ─────────────────────────────────────────────────────


def test_build_temporal_edges_adds_precedence_edge() -> None:
    graph = CausalEventGraph()
    graph.add_node(_make_node("EARLY", ts_offset=0))
    graph.add_node(_make_node("LATE", ts_offset=60))
    edges = build_temporal_edges(graph, propagation_window_seconds=300)
    assert any(
        e.source_id == "EARLY" and e.target_id == "LATE" for e in edges
    )


def test_build_temporal_edges_outside_window_not_added() -> None:
    graph = CausalEventGraph()
    graph.add_node(_make_node("EARLY", ts_offset=0))
    graph.add_node(_make_node("VERY_LATE", ts_offset=3600))
    edges = build_temporal_edges(graph, propagation_window_seconds=300)
    assert edges == []


def test_build_temporal_edges_weight_decreases_with_distance() -> None:
    # Closer events should produce higher weight than distant events
    g_close = CausalEventGraph()
    g_close.add_node(_make_node("X", ts_offset=0))
    g_close.add_node(_make_node("Y", ts_offset=30))
    edges_close = build_temporal_edges(g_close, propagation_window_seconds=300)

    g_far = CausalEventGraph()
    g_far.add_node(_make_node("A", ts_offset=0))
    g_far.add_node(_make_node("B", ts_offset=270))
    edges_far = build_temporal_edges(g_far, propagation_window_seconds=300)

    assert edges_close[0].weight > edges_far[0].weight


# ─── detect_temporal_contradictions ───────────────────────────────────────────


def test_detect_contradiction_deployment_after_anomaly() -> None:
    events = [
        {"event_type": "anomaly", "event_id": "A1", "timestamp_iso": _ts(0)},
        {"event_type": "deployment", "event_id": "D1", "timestamp_iso": _ts(300)},
    ]
    violations = detect_temporal_contradictions(events)
    assert len(violations) == 1
    assert "AFTER anomaly" in violations[0].reason


def test_detect_no_contradiction_deployment_before_anomaly() -> None:
    events = [
        {"event_type": "deployment", "event_id": "D1", "timestamp_iso": _ts(0)},
        {"event_type": "anomaly", "event_id": "A1", "timestamp_iso": _ts(300)},
    ]
    violations = detect_temporal_contradictions(events)
    assert violations == []


def test_detect_no_contradiction_no_deployments() -> None:
    events = [
        {"event_type": "anomaly", "event_id": "A1", "timestamp_iso": _ts(0)},
        {"event_type": "metric_anomaly", "event_id": "M1", "timestamp_iso": _ts(30)},
    ]
    violations = detect_temporal_contradictions(events)
    assert violations == []


# ─── sequence_events_by_time ──────────────────────────────────────────────────


def test_sequence_events_ordered_chronologically() -> None:
    events = [
        {"event_id": "C", "timestamp_iso": _ts(120)},
        {"event_id": "A", "timestamp_iso": _ts(0)},
        {"event_id": "B", "timestamp_iso": _ts(60)},
    ]
    ordered = sequence_events_by_time(events)
    assert [e["event_id"] for e in ordered] == ["A", "B", "C"]


def test_sequence_events_missing_timestamp_sorts_last() -> None:
    events = [
        {"event_id": "NO_TS"},
        {"event_id": "HAS_TS", "timestamp_iso": _ts(0)},
    ]
    ordered = sequence_events_by_time(events)
    assert ordered[0]["event_id"] == "HAS_TS"
    assert ordered[-1]["event_id"] == "NO_TS"


# ─── compute_propagation_lag ──────────────────────────────────────────────────


def test_propagation_lag_positive_for_effect_after_cause() -> None:
    lag = compute_propagation_lag(_ts(0), _ts(120))
    assert lag == pytest.approx(120.0, abs=1.0)


def test_propagation_lag_zero_when_effect_before_cause() -> None:
    lag = compute_propagation_lag(_ts(120), _ts(0))
    assert lag == pytest.approx(0.0)


def test_propagation_lag_zero_for_same_timestamp() -> None:
    ts = _ts(0)
    assert compute_propagation_lag(ts, ts) == pytest.approx(0.0)
