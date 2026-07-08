from __future__ import annotations

from enum import Enum
from typing import Any, List
from pydantic import BaseModel, Field


class KnowledgeNodeType(str, Enum):
    METRIC_ANOMALY = "metric_anomaly"
    LOG_ERROR = "log_error"
    DEPLOYMENT_EVENT = "deployment"
    ALERT = "alert"
    TOPOLOGY_EVENT = "topology"


class KnowledgeEdgeType(str, Enum):
    HAPPENED_BEFORE = "happened_before"
    CAUSED_BY = "caused_by"
    CORRELATED_WITH = "correlated_with"
    DEPENDS_ON = "depends_on"
    SAME_SERVICE = "same_service"
    SAME_HOST = "same_host"
    SAME_TRACE = "same_trace"
    TRIGGERED = "triggered"


class KnowledgeNode(BaseModel):
    id: str
    type: KnowledgeNodeType
    timestamp: str  # ISO timestamp
    service: str
    confidence: float = 1.0
    source: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeEdge(BaseModel):
    source_id: str
    target_id: str
    edge_type: KnowledgeEdgeType
    weight: float = 1.0
    rationale: str = ""


class EvidenceKnowledgeGraph(BaseModel):
    nodes: List[KnowledgeNode] = Field(default_factory=list)
    edges: List[KnowledgeEdge] = Field(default_factory=list)
