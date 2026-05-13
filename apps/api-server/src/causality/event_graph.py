"""
Causal event graph for SentinelOps Phase 43.

Models operational events as nodes in a directed acyclic graph where edges
encode causal influence: temporal precedence, dependency propagation, deployment
linkage, and inferred causal relationships.

Node types:
  metric_anomaly  — metric threshold breach or sudden change
  deployment      — service deployment or configuration change
  alert           — fired alerting rule
  log_event       — log-derived error signature
  topology_event  — service dependency or infrastructure change
  operator_action — manual remediation or escalation

Edge types:
  temporal_precedes  — source event happened before target
  dependency_path    — source service is upstream of target service
  deployment_linked  — deployment co-occurred with anomaly
  causal_influence   — inferred causal contribution
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class NodeType(str, Enum):
    METRIC_ANOMALY = "metric_anomaly"
    DEPLOYMENT = "deployment"
    ALERT = "alert"
    LOG_EVENT = "log_event"
    TOPOLOGY_EVENT = "topology_event"
    OPERATOR_ACTION = "operator_action"


class EdgeType(str, Enum):
    TEMPORAL_PRECEDES = "temporal_precedes"
    DEPENDENCY_PATH = "dependency_path"
    DEPLOYMENT_LINKED = "deployment_linked"
    CAUSAL_INFLUENCE = "causal_influence"


@dataclass
class CausalNode:
    """A single event node in the causal graph."""

    node_id: str
    node_type: NodeType
    service: str
    timestamp_iso: str
    description: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def __hash__(self) -> int:
        return hash(self.node_id)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, CausalNode) and self.node_id == other.node_id


@dataclass
class CausalEdge:
    """A directed edge from source to target encoding causal influence."""

    source_id: str
    target_id: str
    edge_type: EdgeType
    weight: float = 1.0
    rationale: str = ""

    def __hash__(self) -> int:
        return hash((self.source_id, self.target_id, self.edge_type))


class CausalEventGraph:
    """
    Directed graph of operational events with causal edge semantics.

    Edges point FROM cause TO effect (source → target means source caused target).
    """

    def __init__(self) -> None:
        self._nodes: dict[str, CausalNode] = {}
        self._edges: list[CausalEdge] = []

    def add_node(self, node: CausalNode) -> None:
        self._nodes[node.node_id] = node

    def add_edge(self, edge: CausalEdge) -> None:
        if edge.source_id not in self._nodes or edge.target_id not in self._nodes:
            raise ValueError(f"Edge references unknown node: {edge.source_id} → {edge.target_id}")
        self._edges.append(edge)

    @property
    def nodes(self) -> list[CausalNode]:
        return list(self._nodes.values())

    @property
    def edges(self) -> list[CausalEdge]:
        return list(self._edges)

    def get_node(self, node_id: str) -> CausalNode | None:
        return self._nodes.get(node_id)

    def predecessors(self, node_id: str) -> list[CausalNode]:
        """Return all nodes with a causal edge pointing to node_id."""
        ids = {e.source_id for e in self._edges if e.target_id == node_id}
        return [self._nodes[nid] for nid in ids if nid in self._nodes]

    def successors(self, node_id: str) -> list[CausalNode]:
        """Return all nodes that node_id has a causal edge pointing to."""
        ids = {e.target_id for e in self._edges if e.source_id == node_id}
        return [self._nodes[nid] for nid in ids if nid in self._nodes]

    def causal_ancestors(self, node_id: str) -> list[CausalNode]:
        """BFS traversal of all upstream causal ancestors."""
        visited: set[str] = set()
        queue = [node_id]
        result = []
        while queue:
            current = queue.pop(0)
            for pred in self.predecessors(current):
                if pred.node_id not in visited:
                    visited.add(pred.node_id)
                    result.append(pred)
                    queue.append(pred.node_id)
        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [
                {
                    "node_id": n.node_id,
                    "node_type": n.node_type.value,
                    "service": n.service,
                    "timestamp_iso": n.timestamp_iso,
                    "description": n.description,
                }
                for n in self._nodes.values()
            ],
            "edges": [
                {
                    "source_id": e.source_id,
                    "target_id": e.target_id,
                    "edge_type": e.edge_type.value,
                    "weight": e.weight,
                    "rationale": e.rationale,
                }
                for e in self._edges
            ],
        }
