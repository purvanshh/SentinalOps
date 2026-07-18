"""
Causal Reasoning Engine for SentinelOps Phase 6.

Instead of predicting labels from keywords, this module searches for causal
paths through the Evidence Knowledge Graph. It traverses from symptom nodes
backward through `happened_before`, `caused_by`, and `depends_on` edges to
find the deepest originating event — the true root cause.

Pipeline:
    Evidence Graph → Cause Chain Search → Ranked Root Cause Paths
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List

from knowledge.graph_schema import (
    EvidenceKnowledgeGraph,
    KnowledgeEdge,
    KnowledgeEdgeType,
    KnowledgeNode,
    KnowledgeNodeType,
)

# Edge types considered causal (traversable backward to find root causes)
_CAUSAL_EDGE_TYPES = {
    KnowledgeEdgeType.HAPPENED_BEFORE,
    KnowledgeEdgeType.CAUSED_BY,
    KnowledgeEdgeType.DEPENDS_ON,
    KnowledgeEdgeType.TRIGGERED,
}


@dataclass
class CausalPath:
    """A single causal chain from a root event to a symptom."""

    nodes: List[KnowledgeNode]
    edges: List[KnowledgeEdge]
    depth: int
    root_node: KnowledgeNode
    symptom_node: KnowledgeNode
    path_confidence: float = 0.0
    explanation: str = ""

    @property
    def root_service(self) -> str:
        return self.root_node.service

    @property
    def mechanism_type(self) -> str:
        return self.root_node.type.value


@dataclass
class CausalSearchResult:
    """Result of a causal path search through the evidence graph."""

    paths: List[CausalPath] = field(default_factory=list)
    root_events: List[KnowledgeNode] = field(default_factory=list)
    max_depth: int = 0
    search_coverage: float = 0.0

    @property
    def primary_root_cause(self) -> KnowledgeNode | None:
        if not self.paths:
            return None
        best = max(self.paths, key=lambda p: p.path_confidence)
        return best.root_node

    def to_dict(self) -> dict[str, Any]:
        return {
            "paths_found": len(self.paths),
            "root_events": [
                {"id": n.id, "type": n.type.value, "service": n.service}
                for n in self.root_events
            ],
            "max_depth": self.max_depth,
            "search_coverage": self.search_coverage,
        }


class CausalReasoningEngine:
    """
    Searches for causal paths through the Evidence Knowledge Graph.

    Instead of classifying incidents by keyword, this engine performs a
    backward graph traversal from symptom nodes to find originating events.
    Paths are scored by depth, edge weight, and node confidence.
    """

    def __init__(self, graph: EvidenceKnowledgeGraph) -> None:
        self.graph = graph
        self._node_map = {n.id: n for n in graph.nodes}
        self._incoming: dict[str, list[KnowledgeEdge]] = {}
        self._outgoing: dict[str, list[KnowledgeEdge]] = {}
        for edge in graph.edges:
            self._incoming.setdefault(edge.target_id, []).append(edge)
            self._outgoing.setdefault(edge.source_id, []).append(edge)

    def find_symptom_nodes(self) -> list[KnowledgeNode]:
        """Identify leaf symptom nodes (nodes with no outgoing causal edges)."""
        symptoms = []
        for node in self.graph.nodes:
            outgoing_causal = [
                e for e in self._outgoing.get(node.id, [])
                if e.edge_type in _CAUSAL_EDGE_TYPES
            ]
            if not outgoing_causal:
                symptoms.append(node)
        # If no clear symptoms, use the most recent nodes
        if not symptoms:
            sorted_nodes = sorted(self.graph.nodes, key=lambda n: n.timestamp, reverse=True)
            symptoms = sorted_nodes[:3]
        return symptoms

    def find_root_nodes(self) -> list[KnowledgeNode]:
        """Identify root cause candidate nodes (nodes with no incoming causal edges)."""
        roots = []
        for node in self.graph.nodes:
            incoming_causal = [
                e for e in self._incoming.get(node.id, [])
                if e.edge_type in _CAUSAL_EDGE_TYPES
            ]
            if not incoming_causal:
                roots.append(node)
        return roots

    def trace_causal_paths(self, max_depth: int = 10) -> CausalSearchResult:
        """
        Perform backward traversal from symptom nodes to find all causal paths.

        Returns a CausalSearchResult with ranked paths from root events to symptoms.
        """
        symptoms = self.find_symptom_nodes()
        all_paths: list[CausalPath] = []
        root_events_seen: set[str] = set()

        for symptom in symptoms:
            paths = self._backward_search(symptom, max_depth)
            for path in paths:
                all_paths.append(path)
                root_events_seen.add(path.root_node.id)

        # Score and rank paths
        for path in all_paths:
            path.path_confidence = self._score_path(path)
            path.explanation = self._explain_path(path)

        all_paths.sort(key=lambda p: p.path_confidence, reverse=True)

        root_events = [
            self._node_map[rid] for rid in root_events_seen if rid in self._node_map
        ]

        coverage = len(root_events_seen) / max(len(self.graph.nodes), 1)

        return CausalSearchResult(
            paths=all_paths,
            root_events=root_events,
            max_depth=max((p.depth for p in all_paths), default=0),
            search_coverage=round(coverage, 4),
        )

    def _backward_search(
        self,
        symptom: KnowledgeNode,
        max_depth: int,
    ) -> list[CausalPath]:
        """DFS backward from a symptom node through causal edges."""
        paths: list[CausalPath] = []
        stack: list[tuple[str, list[str], list[KnowledgeEdge]]] = [
            (symptom.id, [symptom.id], [])
        ]
        visited_paths: set[tuple[str, ...]] = set()

        while stack:
            current_id, node_chain, edge_chain = stack.pop()
            if len(node_chain) > max_depth:
                continue

            incoming = [
                e for e in self._incoming.get(current_id, [])
                if e.edge_type in _CAUSAL_EDGE_TYPES
            ]

            if not incoming:
                # This is a root node — record the path
                path_key = tuple(node_chain)
                if path_key not in visited_paths and len(node_chain) > 1:
                    visited_paths.add(path_key)
                    path_nodes = [
                        self._node_map[nid] for nid in reversed(node_chain)
                        if nid in self._node_map
                    ]
                    paths.append(CausalPath(
                        nodes=path_nodes,
                        edges=list(reversed(edge_chain)),
                        depth=len(node_chain) - 1,
                        root_node=path_nodes[0],
                        symptom_node=path_nodes[-1],
                    ))
            else:
                for edge in incoming:
                    if edge.source_id not in node_chain:
                        stack.append((
                            edge.source_id,
                            node_chain + [edge.source_id],
                            edge_chain + [edge],
                        ))

        return paths

    def _score_path(self, path: CausalPath) -> float:
        """Score a causal path based on depth, edge weights, and node confidence."""
        if not path.edges:
            return 0.0

        # Average edge weight
        avg_weight = sum(e.weight for e in path.edges) / len(path.edges)

        # Average node confidence
        avg_confidence = sum(n.confidence for n in path.nodes) / len(path.nodes)

        # Depth bonus: longer chains that hold together are more convincing
        depth_factor = min(1.0, path.depth / 5.0)

        # Deployment root bonus: if root is a deployment, higher confidence
        deploy_bonus = 0.15 if path.root_node.type == KnowledgeNodeType.DEPLOYMENT_EVENT else 0.0

        score = (avg_weight * 0.35) + (avg_confidence * 0.30) + (depth_factor * 0.20) + deploy_bonus
        return round(min(1.0, score), 4)

    def _explain_path(self, path: CausalPath) -> str:
        """Generate a human-readable explanation of a causal path."""
        if not path.nodes:
            return "Empty causal path"

        steps = []
        for i, node in enumerate(path.nodes):
            prefix = "ROOT: " if i == 0 else "  → "
            desc = node.metadata.get('description', node.id)
            steps.append(f"{prefix}[{node.type.value}] {node.service}: {desc}")

        return " ".join(steps)
