"""
Topology-aware propagation estimation for SentinelOps Phase 43.

Models how failures travel through service dependency graphs:
  - blast radius: set of services reachable from a failing service
  - propagation path: ordered sequence of services in the failure chain
  - amplification factor: how many services are affected per hop
  - critical path detection: longest failure chain in the dependency graph

This module adds DEPENDENCY_PATH edges to a CausalEventGraph based on the
service topology, allowing the causal reasoning engine to distinguish:
  - primary failure origin (upstream source with no causal predecessors)
  - secondary effects (downstream services that received blast)
  - collateral services (not on any path from the origin)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from causality.event_graph import CausalEdge, CausalEventGraph, CausalNode, EdgeType


@dataclass
class PropagationResult:
    """Result of a blast propagation analysis."""
    origin_service: str
    blast_radius: list[str]
    propagation_paths: list[list[str]]
    max_depth: int
    amplification_factor: float
    critical_path: list[str] = field(default_factory=list)

    @property
    def is_contained(self) -> bool:
        """True when blast radius is limited to a single service."""
        return len(self.blast_radius) <= 1


def _downstream_services(
    service: str,
    topology: dict[str, Any],
    *,
    max_depth: int = 5,
) -> set[str]:
    """BFS to find all services reachable downstream from service."""
    deps = topology.get("dependencies", {})
    visited: set[str] = set()
    queue = [service]
    depth = 0
    while queue and depth < max_depth:
        next_queue = []
        for svc in queue:
            for target in deps.get(svc, []):
                if target not in visited:
                    visited.add(target)
                    next_queue.append(target)
        queue = next_queue
        depth += 1
    return visited


def _all_paths(
    source: str,
    topology: dict[str, Any],
    *,
    max_depth: int = 5,
) -> list[list[str]]:
    """DFS to enumerate all dependency paths starting from source."""
    deps = topology.get("dependencies", {})
    results: list[list[str]] = []

    def dfs(current: str, path: list[str], depth: int) -> None:
        if depth > max_depth:
            return
        targets = deps.get(current, [])
        if not targets:
            results.append(list(path))
            return
        for target in targets:
            if target not in path:
                dfs(target, path + [target], depth + 1)

    dfs(source, [source], 0)
    return results or [[source]]


class PropagationEstimator:
    """
    Estimates failure propagation across a service topology.

    Given an originating service and a topology graph, computes:
      - which services are reachable (blast radius)
      - what paths the failure travels
      - how deeply it propagates
    """

    def __init__(self, topology: dict[str, Any]) -> None:
        self._topology = topology

    def estimate(
        self,
        origin_service: str,
        *,
        max_depth: int = 5,
    ) -> PropagationResult:
        """Compute propagation starting from origin_service."""
        blast = _downstream_services(origin_service, self._topology, max_depth=max_depth)
        paths = _all_paths(origin_service, self._topology, max_depth=max_depth)
        max_path_len = max((len(p) for p in paths), default=1)
        amplification = len(blast) / max(max_path_len, 1)
        critical_path = max(paths, key=len, default=[origin_service])

        return PropagationResult(
            origin_service=origin_service,
            blast_radius=sorted(blast),
            propagation_paths=paths,
            max_depth=max_path_len - 1,
            amplification_factor=round(amplification, 2),
            critical_path=critical_path,
        )

    def add_topology_edges(
        self,
        graph: CausalEventGraph,
        service_to_node: dict[str, str],
    ) -> list[CausalEdge]:
        """
        For each topology dependency, add a DEPENDENCY_PATH edge in the graph
        if both services have nodes in service_to_node.

        service_to_node maps service_name → node_id in the graph.
        Returns list of added edges.
        """
        deps = self._topology.get("dependencies", {})
        added: list[CausalEdge] = []
        for source_svc, targets in deps.items():
            source_node_id = service_to_node.get(source_svc)
            if not source_node_id:
                continue
            for target_svc in targets:
                target_node_id = service_to_node.get(target_svc)
                if not target_node_id:
                    continue
                edge = CausalEdge(
                    source_id=source_node_id,
                    target_id=target_node_id,
                    edge_type=EdgeType.DEPENDENCY_PATH,
                    weight=0.8,
                    rationale=(
                        f"{source_svc} is a direct upstream dependency of {target_svc}"
                    ),
                )
                graph.add_edge(edge)
                added.append(edge)
        return added
