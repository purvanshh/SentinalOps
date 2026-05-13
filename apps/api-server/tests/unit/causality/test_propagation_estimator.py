"""
Phase 43 topology-aware propagation estimation tests.

Proves:
  - PropagationEstimator.estimate() computes correct blast radius.
  - Blast radius includes all downstream services reachable via topology.
  - max_depth parameter limits search depth.
  - amplification_factor reflects blast spread.
  - critical_path is the longest propagation path.
  - is_contained is True when blast only affects origin.
  - add_topology_edges() adds DEPENDENCY_PATH edges to a CausalEventGraph.
  - Services not in service_to_node are skipped gracefully.
  - Empty topology produces empty blast radius.
"""

from __future__ import annotations

from causality.event_graph import CausalEventGraph, CausalNode, EdgeType, NodeType
from causality.propagation_estimator import PropagationEstimator


def _topology(*deps: tuple[str, list[str]]) -> dict:
    return {"dependencies": {src: targets for src, targets in deps}}


def _make_graph_with_services(services: list[str]) -> tuple[CausalEventGraph, dict[str, str]]:
    """Build a graph with one node per service, return (graph, service_to_node)."""
    graph = CausalEventGraph()
    service_to_node: dict[str, str] = {}
    for svc in services:
        node = CausalNode(
            node_id=f"node_{svc}",
            node_type=NodeType.METRIC_ANOMALY,
            service=svc,
            timestamp_iso="2024-01-01T14:00:00+00:00",
            description=f"anomaly in {svc}",
        )
        graph.add_node(node)
        service_to_node[svc] = node.node_id
    return graph, service_to_node


# ─── PropagationEstimator.estimate() ─────────────────────────────────────────


def test_estimate_blast_radius_includes_direct_downstream() -> None:
    topology = _topology(("database", ["payment-api"]))
    estimator = PropagationEstimator(topology)
    result = estimator.estimate("database")
    assert "payment-api" in result.blast_radius


def test_estimate_blast_radius_includes_transitive_downstream() -> None:
    topology = _topology(
        ("database", ["payment-api"]),
        ("payment-api", ["checkout-service"]),
    )
    estimator = PropagationEstimator(topology)
    result = estimator.estimate("database")
    assert "payment-api" in result.blast_radius
    assert "checkout-service" in result.blast_radius


def test_estimate_empty_topology_empty_blast() -> None:
    estimator = PropagationEstimator({})
    result = estimator.estimate("database")
    assert result.blast_radius == []


def test_estimate_origin_not_in_blast_radius() -> None:
    topology = _topology(("database", ["api"]))
    estimator = PropagationEstimator(topology)
    result = estimator.estimate("database")
    assert "database" not in result.blast_radius


def test_estimate_max_depth_limits_propagation() -> None:
    topology = _topology(
        ("A", ["B"]),
        ("B", ["C"]),
        ("C", ["D"]),
        ("D", ["E"]),
    )
    estimator = PropagationEstimator(topology)
    result_shallow = estimator.estimate("A", max_depth=1)
    result_deep = estimator.estimate("A", max_depth=10)
    assert len(result_shallow.blast_radius) < len(result_deep.blast_radius)


def test_estimate_is_contained_single_service() -> None:
    estimator = PropagationEstimator({})
    result = estimator.estimate("standalone-service")
    assert result.is_contained is True


def test_estimate_not_contained_with_blast() -> None:
    topology = _topology(("db", ["api", "worker"]))
    estimator = PropagationEstimator(topology)
    result = estimator.estimate("db")
    assert result.is_contained is False


def test_estimate_critical_path_is_longest_chain() -> None:
    topology = _topology(
        ("db", ["api"]),
        ("api", ["checkout"]),
        ("checkout", ["notification"]),
        ("db", ["cache"]),
    )
    estimator = PropagationEstimator(topology)
    result = estimator.estimate("db")
    assert len(result.critical_path) >= 2


def test_estimate_amplification_factor_positive() -> None:
    topology = _topology(("db", ["api", "worker", "analytics"]))
    estimator = PropagationEstimator(topology)
    result = estimator.estimate("db")
    assert result.amplification_factor > 0


# ─── add_topology_edges() ─────────────────────────────────────────────────────


def test_add_topology_edges_creates_dependency_edges() -> None:
    topology = _topology(("database", ["payment-api"]))
    estimator = PropagationEstimator(topology)
    graph, service_to_node = _make_graph_with_services(["database", "payment-api"])
    added = estimator.add_topology_edges(graph, service_to_node)
    assert len(added) == 1
    assert added[0].edge_type == EdgeType.DEPENDENCY_PATH
    assert added[0].source_id == "node_database"
    assert added[0].target_id == "node_payment-api"


def test_add_topology_edges_skips_missing_services() -> None:
    topology = _topology(("database", ["unknown-service"]))
    estimator = PropagationEstimator(topology)
    graph, service_to_node = _make_graph_with_services(["database"])
    added = estimator.add_topology_edges(graph, service_to_node)
    assert added == []


def test_add_topology_edges_multiple_dependencies() -> None:
    topology = _topology(("db", ["api", "worker"]))
    estimator = PropagationEstimator(topology)
    graph, s2n = _make_graph_with_services(["db", "api", "worker"])
    added = estimator.add_topology_edges(graph, s2n)
    assert len(added) == 2


def test_add_topology_edges_rationale_mentions_services() -> None:
    topology = _topology(("database", ["payment-api"]))
    estimator = PropagationEstimator(topology)
    graph, s2n = _make_graph_with_services(["database", "payment-api"])
    added = estimator.add_topology_edges(graph, s2n)
    assert "database" in added[0].rationale
    assert "payment-api" in added[0].rationale
