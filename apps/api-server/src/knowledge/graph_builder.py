from __future__ import annotations

from datetime import datetime
from typing import Any
from knowledge.graph_schema import (
    EvidenceKnowledgeGraph,
    KnowledgeEdge,
    KnowledgeEdgeType,
    KnowledgeNode,
    KnowledgeNodeType,
)


def build_knowledge_graph(
    evidence_items: list[dict[str, Any]] | list[Any],
    topology: Any = None,
) -> EvidenceKnowledgeGraph:
    """Build a correlated Knowledge Graph from flat evidence items and system topology."""
    nodes = []
    edges = []

    # 1. Map all evidence items to KnowledgeNodes
    for item in evidence_items:
        if hasattr(item, "model_dump"):
            data = item.model_dump()
        elif isinstance(item, dict):
            data = item
        else:
            continue

        item_id = str(data.get("evidence_id") or data.get("id") or "")
        if not item_id:
            continue

        source = data.get("source", "")
        # Map source to NodeType
        node_type = KnowledgeNodeType.METRIC_ANOMALY
        if source == "logs" or "log" in source:
            node_type = KnowledgeNodeType.LOG_ERROR
        elif source == "deployment" or "deploy" in source:
            node_type = KnowledgeNodeType.DEPLOYMENT_EVENT
        elif source == "metrics" or "metric" in source:
            node_type = KnowledgeNodeType.METRIC_ANOMALY
        elif source == "alerts" or "alert" in source:
            node_type = KnowledgeNodeType.ALERT

        nodes.append(
            KnowledgeNode(
                id=item_id,
                type=node_type,
                timestamp=data.get("timestamp") or datetime.utcnow().isoformat(),
                service=data.get("service") or "unknown",
                confidence=float(data.get("confidence") or 1.0),
                source=source,
                metadata=data.get("metadata") or {},
            )
        )

    # 2. Add structural & temporal edges between nodes
    for i in range(len(nodes)):
        node_a = nodes[i]
        for j in range(i + 1, len(nodes)):
            node_b = nodes[j]

            # Determine order based on timestamps
            try:
                t_a = datetime.fromisoformat(node_a.timestamp.replace("Z", "+00:00"))
                t_b = datetime.fromisoformat(node_b.timestamp.replace("Z", "+00:00"))
            except Exception:
                continue

            earlier, later = (node_a, node_b) if t_a <= t_b else (node_b, node_a)
            delta = abs((t_a - t_b).total_seconds())

            # a) Happened before (if within 15 minutes)
            if delta < 900:
                edges.append(
                    KnowledgeEdge(
                        source_id=earlier.id,
                        target_id=later.id,
                        edge_type=KnowledgeEdgeType.HAPPENED_BEFORE,
                        weight=max(0.1, 1.0 - (delta / 900.0)),
                        rationale=f"{earlier.source} event happened {delta:.1f}s before {later.source} event",
                    )
                )

            # b) Same service linkage
            if node_a.service == node_b.service and node_a.service != "unknown":
                edges.append(
                    KnowledgeEdge(
                        source_id=node_a.id,
                        target_id=node_b.id,
                        edge_type=KnowledgeEdgeType.SAME_SERVICE,
                        weight=1.0,
                        rationale=f"Both events occurred on the same service: {node_a.service}",
                    )
                )

            # c) Topology dependency linkage
            if topology is not None:
                dep_a_calls_b = False
                dep_b_calls_a = False
                if hasattr(topology, "has_edge"):
                    dep_a_calls_b = topology.has_edge(node_a.service, node_b.service)
                    dep_b_calls_a = topology.has_edge(node_b.service, node_a.service)
                elif isinstance(topology, dict):
                    dep_a_calls_b = node_b.service in topology.get(node_a.service, [])
                    dep_b_calls_a = node_a.service in topology.get(node_b.service, [])

                if dep_a_calls_b:
                    edges.append(
                        KnowledgeEdge(
                            source_id=node_a.id,
                            target_id=node_b.id,
                            edge_type=KnowledgeEdgeType.DEPENDS_ON,
                            weight=0.8,
                            rationale=f"Service {node_a.service} depends on {node_b.service}",
                        )
                    )
                if dep_b_calls_a:
                    edges.append(
                        KnowledgeEdge(
                            source_id=node_b.id,
                            target_id=node_a.id,
                            edge_type=KnowledgeEdgeType.DEPENDS_ON,
                            weight=0.8,
                            rationale=f"Service {node_b.service} depends on {node_a.service}",
                        )
                    )

    return EvidenceKnowledgeGraph(nodes=nodes, edges=edges)
