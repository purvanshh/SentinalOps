from __future__ import annotations

from typing import List

from knowledge.graph_schema import (
    EvidenceKnowledgeGraph,
    KnowledgeEdge,
    KnowledgeEdgeType,
    KnowledgeNode,
)


class GraphQuery:
    """Helper class to query and traverse the EvidenceKnowledgeGraph."""

    def __init__(self, graph: EvidenceKnowledgeGraph) -> None:
        self.graph = graph
        self._node_map = {n.id: n for n in graph.nodes}

    def get_node(self, node_id: str) -> KnowledgeNode | None:
        return self._node_map.get(node_id)

    def get_edges_from(self, node_id: str) -> List[KnowledgeEdge]:
        return [e for e in self.graph.edges if e.source_id == node_id]

    def get_edges_to(self, node_id: str) -> List[KnowledgeEdge]:
        return [e for e in self.graph.edges if e.target_id == node_id]

    def get_successors(
        self, node_id: str, edge_type: KnowledgeEdgeType | None = None
    ) -> List[KnowledgeNode]:
        successors = []
        for e in self.get_edges_from(node_id):
            if edge_type is None or e.edge_type == edge_type:
                node = self.get_node(e.target_id)
                if node:
                    successors.append(node)
        return successors

    def get_predecessors(
        self, node_id: str, edge_type: KnowledgeEdgeType | None = None
    ) -> List[KnowledgeNode]:
        predecessors = []
        for e in self.get_edges_to(node_id):
            if edge_type is None or e.edge_type == edge_type:
                node = self.get_node(e.source_id)
                if node:
                    predecessors.append(node)
        return predecessors

    def trace_upstream_causes(self, node_id: str) -> List[KnowledgeNode]:
        """BFS search to trace all upstream events that happened before this node."""
        visited = set()
        queue = [node_id]
        causes = []
        while queue:
            curr = queue.pop(0)
            preds = self.get_predecessors(curr, KnowledgeEdgeType.HAPPENED_BEFORE)
            for p in preds:
                if p.id not in visited:
                    visited.add(p.id)
                    causes.append(p)
                    queue.append(p.id)
        return causes
