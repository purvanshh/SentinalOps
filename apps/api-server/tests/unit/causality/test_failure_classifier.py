"""
Phase 43 primary vs secondary failure classification tests.

Validates scenario A (cascading failure: postgres → API):
  - postgres failure → PRIMARY_CAUSE
  - API latency → SECONDARY_EFFECT

Validates scenario C (collateral noise):
  - unrelated alert with no causal edges → COLLATERAL_NOISE

Validates scenario D (operator action):
  - NodeType.OPERATOR_ACTION → OPERATOR_ACTION

Also proves:
  - Cascading failures at depth >= 2 classified as CASCADING_FAILURE.
  - filter_by_type, primary_causes, secondary_effects helpers work.
  - to_classification_dict produces serializable output.
"""

from __future__ import annotations

from causality.event_graph import (
    CausalEdge,
    CausalEventGraph,
    CausalNode,
    EdgeType,
    NodeType,
)
from causality.failure_classifier import (
    FailureType,
    classify_failures,
    collateral_noise,
    filter_by_type,
    primary_causes,
    secondary_effects,
    to_classification_dict,
)


def _make_node(
    node_id: str,
    node_type: NodeType = NodeType.METRIC_ANOMALY,
    service: str = "payment-api",
) -> CausalNode:
    return CausalNode(
        node_id=node_id,
        node_type=node_type,
        service=service,
        timestamp_iso="2024-01-01T14:00:00+00:00",
        description=f"event {node_id}",
    )


def _connect(graph: CausalEventGraph, src: str, dst: str) -> None:
    graph.add_edge(CausalEdge(src, dst, EdgeType.CAUSAL_INFLUENCE))


# ─── Scenario B: cascading failure (postgres → API) ───────────────────────────


def test_classify_postgres_as_primary_cause() -> None:
    graph = CausalEventGraph()
    graph.add_node(_make_node("DB", service="database"))
    graph.add_node(_make_node("API", service="payment-api"))
    _connect(graph, "DB", "API")

    classified = classify_failures(graph)
    db_cls = next(c for c in classified if c.node.node_id == "DB")
    assert db_cls.failure_type == FailureType.PRIMARY_CAUSE


def test_classify_api_latency_as_secondary_effect() -> None:
    graph = CausalEventGraph()
    graph.add_node(_make_node("DB", service="database"))
    graph.add_node(_make_node("API", service="payment-api"))
    _connect(graph, "DB", "API")

    classified = classify_failures(graph)
    api_cls = next(c for c in classified if c.node.node_id == "API")
    assert api_cls.failure_type == FailureType.SECONDARY_EFFECT


def test_classify_deep_chain_as_cascading_failure() -> None:
    graph = CausalEventGraph()
    graph.add_node(_make_node("ROOT"))
    graph.add_node(_make_node("MID"))
    graph.add_node(_make_node("LEAF"))
    _connect(graph, "ROOT", "MID")
    _connect(graph, "MID", "LEAF")

    classified = classify_failures(graph)
    leaf_cls = next(c for c in classified if c.node.node_id == "LEAF")
    assert leaf_cls.failure_type == FailureType.CASCADING_FAILURE
    assert leaf_cls.causal_depth >= 2


# ─── Scenario C: collateral noise ────────────────────────────────────────────


def test_classify_isolated_node_as_collateral_noise() -> None:
    graph = CausalEventGraph()
    graph.add_node(_make_node("NOISY"))
    classified = classify_failures(graph)
    assert classified[0].failure_type == FailureType.COLLATERAL_NOISE


def test_collateral_noise_helper_returns_isolated_nodes() -> None:
    graph = CausalEventGraph()
    graph.add_node(_make_node("DB"))
    graph.add_node(_make_node("NOISY"))
    graph.add_node(_make_node("API"))
    _connect(graph, "DB", "API")

    classified = classify_failures(graph)
    noise = collateral_noise(classified)
    assert any(c.node.node_id == "NOISY" for c in noise)


# ─── Scenario D (operator action) ────────────────────────────────────────────


def test_classify_operator_action_node_type() -> None:
    graph = CausalEventGraph()
    graph.add_node(_make_node("ROLLBACK", node_type=NodeType.OPERATOR_ACTION))
    classified = classify_failures(graph)
    assert classified[0].failure_type == FailureType.OPERATOR_ACTION


# ─── filter helpers ──────────────────────────────────────────────────────────


def test_primary_causes_helper_returns_only_primaries() -> None:
    graph = CausalEventGraph()
    graph.add_node(_make_node("DB"))
    graph.add_node(_make_node("API"))
    _connect(graph, "DB", "API")

    classified = classify_failures(graph)
    primaries = primary_causes(classified)
    assert all(c.failure_type == FailureType.PRIMARY_CAUSE for c in primaries)
    assert any(c.node.node_id == "DB" for c in primaries)


def test_secondary_effects_helper_returns_only_secondaries() -> None:
    graph = CausalEventGraph()
    graph.add_node(_make_node("DB"))
    graph.add_node(_make_node("API"))
    _connect(graph, "DB", "API")

    classified = classify_failures(graph)
    secondaries = secondary_effects(classified)
    assert all(c.failure_type == FailureType.SECONDARY_EFFECT for c in secondaries)


def test_filter_by_type_empty_graph() -> None:
    graph = CausalEventGraph()
    classified = classify_failures(graph)
    assert filter_by_type(classified, failure_type=FailureType.PRIMARY_CAUSE) == []


# ─── to_classification_dict ───────────────────────────────────────────────────


def test_to_classification_dict_includes_all_keys() -> None:
    graph = CausalEventGraph()
    graph.add_node(_make_node("DB"))
    graph.add_node(_make_node("API"))
    _connect(graph, "DB", "API")

    classified = classify_failures(graph)
    d = to_classification_dict(classified)
    assert "primary_causes" in d
    assert "secondary_effects" in d
    assert "collateral_noise" in d
    assert "all_classified" in d


def test_to_classification_dict_has_correct_counts() -> None:
    graph = CausalEventGraph()
    graph.add_node(_make_node("DB"))
    graph.add_node(_make_node("API"))
    graph.add_node(_make_node("NOISY"))
    _connect(graph, "DB", "API")

    classified = classify_failures(graph)
    d = to_classification_dict(classified)
    assert len(d["primary_causes"]) == 1
    assert len(d["secondary_effects"]) == 1
    assert len(d["collateral_noise"]) == 1


def test_all_classified_entries_have_failure_type() -> None:
    graph = CausalEventGraph()
    graph.add_node(_make_node("A"))
    graph.add_node(_make_node("B"))
    _connect(graph, "A", "B")

    classified = classify_failures(graph)
    d = to_classification_dict(classified)
    for entry in d["all_classified"]:
        assert "failure_type" in entry
        assert entry["failure_type"] in [ft.value for ft in FailureType]
