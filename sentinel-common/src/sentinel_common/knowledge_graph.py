"""Causal Knowledge Graph — explicit infrastructure causality for root-cause analysis.

Replaces generic LLM reasoning with structured causal relationships between
infrastructure entities. Supports temporal traversal for incident investigation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class EntityType(Enum):
    SERVICE = "service"
    DATABASE = "database"
    QUEUE = "queue"
    DEPLOYMENT = "deployment"
    FEATURE_FLAG = "feature_flag"
    ALERT = "alert"
    LOG_PATTERN = "log_pattern"
    METRIC = "metric"
    USER = "user"
    ENDPOINT = "endpoint"
    NODE = "node"


class EdgeType(Enum):
    DEPENDS_ON = "depends_on"
    TRIGGERS = "triggers"
    DEPLOYED_WITH = "deployed_with"
    FAILED_AFTER = "failed_after"
    COMMUNICATES_WITH = "communicates_with"
    SATURATES = "saturates"
    READS_FROM = "reads_from"
    WRITES_TO = "writes_to"
    SCALES_WITH = "scales_with"
    ALERTS_ON = "alerts_on"


@dataclass
class GraphEntity:
    id: str
    entity_type: EntityType
    name: str
    properties: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CausalEdge:
    source_id: str
    target_id: str
    edge_type: EdgeType
    weight: float = 1.0
    timestamp: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CausalPath:
    """A chain of causal relationships from trigger to impact."""

    edges: list[CausalEdge]
    total_weight: float = 0.0
    start_time: datetime | None = None
    end_time: datetime | None = None

    @property
    def length(self) -> int:
        return len(self.edges)

    @property
    def entity_ids(self) -> list[str]:
        if not self.edges:
            return []
        ids = [self.edges[0].source_id]
        ids.extend(e.target_id for e in self.edges)
        return ids


class CausalKnowledgeGraph:
    """In-memory causal knowledge graph with temporal traversal.

    For production, back with Neo4j or Memgraph via GraphBackend.
    """

    def __init__(self) -> None:
        self._entities: dict[str, GraphEntity] = {}
        self._edges: list[CausalEdge] = []
        self._adjacency: dict[str, list[CausalEdge]] = {}
        self._reverse_adjacency: dict[str, list[CausalEdge]] = {}

    def add_entity(self, entity: GraphEntity) -> None:
        self._entities[entity.id] = entity
        if entity.id not in self._adjacency:
            self._adjacency[entity.id] = []
            self._reverse_adjacency[entity.id] = []

    def add_edge(self, edge: CausalEdge) -> None:
        self._edges.append(edge)
        self._adjacency.setdefault(edge.source_id, []).append(edge)
        self._reverse_adjacency.setdefault(edge.target_id, []).append(edge)

    def get_entity(self, entity_id: str) -> GraphEntity | None:
        return self._entities.get(entity_id)

    def get_dependencies(self, entity_id: str) -> list[GraphEntity]:
        """Get entities this entity depends on."""
        edges = self._adjacency.get(entity_id, [])
        dep_edges = [e for e in edges if e.edge_type == EdgeType.DEPENDS_ON]
        return [self._entities[e.target_id] for e in dep_edges if e.target_id in self._entities]

    def get_dependents(self, entity_id: str) -> list[GraphEntity]:
        """Get entities that depend on this entity."""
        edges = self._reverse_adjacency.get(entity_id, [])
        dep_edges = [e for e in edges if e.edge_type == EdgeType.DEPENDS_ON]
        return [self._entities[e.source_id] for e in dep_edges if e.source_id in self._entities]

    def traverse_causal_chain(
        self, start_id: str, max_depth: int = 10, edge_types: list[EdgeType] | None = None
    ) -> list[CausalPath]:
        """Forward traversal: find all causal paths from a starting entity."""
        paths: list[CausalPath] = []
        self._dfs_forward(start_id, [], 0.0, max_depth, edge_types, paths)
        return sorted(paths, key=lambda p: p.total_weight, reverse=True)

    def trace_root_causes(
        self, impact_id: str, max_depth: int = 10, edge_types: list[EdgeType] | None = None
    ) -> list[CausalPath]:
        """Backward traversal: trace from impact back to root causes."""
        paths: list[CausalPath] = []
        self._dfs_backward(impact_id, [], 0.0, max_depth, edge_types, paths)
        return sorted(paths, key=lambda p: p.total_weight, reverse=True)

    def temporal_causal_traversal(
        self, start_id: str, time_window_start: datetime, time_window_end: datetime
    ) -> list[CausalPath]:
        """Traverse causal chains within a time window."""
        paths: list[CausalPath] = []
        self._dfs_temporal(start_id, [], 0.0, time_window_start, time_window_end, set(), paths)
        return sorted(paths, key=lambda p: p.total_weight, reverse=True)

    def get_blast_radius(self, entity_id: str, max_depth: int = 5) -> list[GraphEntity]:
        """Get all entities potentially impacted by failure of given entity."""
        visited: set[str] = set()
        queue = [entity_id]
        while queue and len(visited) < 100:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            for edge in self._reverse_adjacency.get(current, []):
                if edge.edge_type in (EdgeType.DEPENDS_ON, EdgeType.COMMUNICATES_WITH):
                    if edge.source_id not in visited and len(visited) < max_depth * 10:
                        queue.append(edge.source_id)
        visited.discard(entity_id)
        return [self._entities[eid] for eid in visited if eid in self._entities]

    def _dfs_forward(
        self,
        current: str,
        path: list[CausalEdge],
        weight: float,
        max_depth: int,
        edge_types: list[EdgeType] | None,
        results: list[CausalPath],
    ) -> None:
        if len(path) >= max_depth:
            return
        edges = self._adjacency.get(current, [])
        if edge_types:
            edges = [e for e in edges if e.edge_type in edge_types]
        if not edges and path:
            results.append(CausalPath(edges=list(path), total_weight=weight))
            return
        for edge in edges:
            if any(e.target_id == edge.target_id for e in path):
                continue
            path.append(edge)
            self._dfs_forward(
                edge.target_id, path, weight + edge.weight, max_depth, edge_types, results
            )
            path.pop()

    def _dfs_backward(
        self,
        current: str,
        path: list[CausalEdge],
        weight: float,
        max_depth: int,
        edge_types: list[EdgeType] | None,
        results: list[CausalPath],
    ) -> None:
        if len(path) >= max_depth:
            return
        edges = self._reverse_adjacency.get(current, [])
        if edge_types:
            edges = [e for e in edges if e.edge_type in edge_types]
        if not edges and path:
            results.append(CausalPath(edges=list(reversed(path)), total_weight=weight))
            return
        for edge in edges:
            if any(e.source_id == edge.source_id for e in path):
                continue
            path.append(edge)
            self._dfs_backward(
                edge.source_id, path, weight + edge.weight, max_depth, edge_types, results
            )
            path.pop()

    def _dfs_temporal(
        self,
        current: str,
        path: list[CausalEdge],
        weight: float,
        t_start: datetime,
        t_end: datetime,
        visited: set[str],
        results: list[CausalPath],
    ) -> None:
        if len(path) >= 10 or current in visited:
            return
        visited.add(current)
        edges = self._adjacency.get(current, [])
        temporal_edges = [e for e in edges if e.timestamp and t_start <= e.timestamp <= t_end]
        if not temporal_edges and path:
            results.append(
                CausalPath(
                    edges=list(path),
                    total_weight=weight,
                    start_time=t_start,
                    end_time=t_end,
                )
            )
            return
        for edge in temporal_edges:
            path.append(edge)
            self._dfs_temporal(
                edge.target_id, path, weight + edge.weight, t_start, t_end, visited, results
            )
            path.pop()
        visited.discard(current)
