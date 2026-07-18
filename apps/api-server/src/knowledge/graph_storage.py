from __future__ import annotations

import json

from knowledge.graph_schema import EvidenceKnowledgeGraph


def serialize_graph(graph: EvidenceKnowledgeGraph) -> str:
    """Serialize the EvidenceKnowledgeGraph to a JSON string."""
    return graph.model_dump_json()


def deserialize_graph(serialized: str) -> EvidenceKnowledgeGraph:
    """Deserialize a JSON string back to an EvidenceKnowledgeGraph."""
    try:
        data = json.loads(serialized)
        return EvidenceKnowledgeGraph.model_validate(data)
    except Exception:
        return EvidenceKnowledgeGraph(nodes=[], edges=[])
