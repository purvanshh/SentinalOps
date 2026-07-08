"""
Operational memory layer for SentinelOps.

Provides six categorized memory stores that persist operational knowledge
across incident lifecycles:

  incident_memory    — semantically similar historical incidents
  remediation_memory — successful remediation patterns and outcomes
  deployment_memory  — deployment-related regression patterns
  topology_memory    — dependency-related failure cascades
  noisy_alert_memory — false-positive and low-signal alert patterns
  escalation_memory  — incidents that required operator escalation

Each memory category supports:
  - store(key, payload) — write a resolved event to memory
  - recall(query, limit) — retrieve semantically similar events
  - recall returns typed MemoryItem with provenance fields

This layer is intentionally stateless at construction: all persistence is
delegated to Qdrant collections via the retrieval layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from core.config import get_settings
from retrieval.embeddings.collection_manager import CollectionSpec, QdrantCollectionManager
from retrieval.embeddings.embedding_client import EmbeddingClient


@dataclass
class MemoryItem:
    """A retrieved memory entry with full provenance."""

    key: str
    category: str
    payload: dict[str, Any]
    similarity_score: float
    retrieved_at: str
    embedding_model: str
    retrieval_reason: str = ""

    @classmethod
    def from_qdrant_result(
        cls,
        item: dict[str, Any],
        *,
        category: str,
        embedding_model: str,
    ) -> "MemoryItem":
        payload = item.get("payload") or {}
        score = float(item.get("score") or 0.0)
        key = payload.get("key", payload.get("incident_id", ""))
        return cls(
            key=key,
            category=category,
            payload=payload,
            similarity_score=round(score, 4),
            retrieved_at=datetime.now(UTC).isoformat(),
            embedding_model=embedding_model,
            retrieval_reason=_reason_for_score(score),
        )


def _reason_for_score(score: float) -> str:
    if score >= 0.90:
        return "high-confidence semantic match"
    if score >= 0.75:
        return "moderate semantic similarity"
    if score >= 0.50:
        return "weak semantic relevance"
    return "low-confidence match — review carefully"


class _MemoryStore:
    """Single-category memory store backed by a Qdrant collection."""

    def __init__(
        self,
        *,
        collection_name: str,
        category: str,
        embedding_client: EmbeddingClient,
        collection_manager: QdrantCollectionManager,
    ) -> None:
        self.collection_name = collection_name
        self.category = category
        self._embedding = embedding_client
        self._qdrant = collection_manager

    async def store(self, key: str, payload: dict[str, Any]) -> bool:
        """Embed and upsert a memory entry."""
        text = _payload_to_text(payload)
        vector = await self._embedding.embed_text_async(text)
        return await self._qdrant.upsert_points_async(
            self.collection_name,
            [{"id": key, "vector": vector, "payload": {"key": key, **payload}}],
        )

    async def recall(self, query: str, limit: int = 3) -> list[MemoryItem]:
        """Retrieve semantically similar memory entries."""
        vector = await self._embedding.embed_text_async(query)
        results = await self._qdrant.search_async(self.collection_name, vector, limit=limit)
        return [
            MemoryItem.from_qdrant_result(
                item,
                category=self.category,
                embedding_model=self._embedding.active_model,
            )
            for item in results
        ]

    async def recall_structured(
        self,
        query: str,
        graph: Any = None,
        service: str = "unknown",
        topology: Any = None,
        limit: int = 3,
    ) -> list[MemoryItem]:
        """Retrieve historical memories and re-rank them using multi-dimensional context."""
        items = await self.recall(query, limit=limit * 2)

        # Re-rank items using structural overlap
        ranked_items = []
        for item in items:
            payload = item.payload
            structural_score = 0.0

            # 1. Service dependency overlap
            historical_service = payload.get("service") or "unknown"
            if service != "unknown" and historical_service != "unknown":
                if service == historical_service:
                    structural_score += 0.25
                elif topology is not None:
                    is_dep = False
                    if hasattr(topology, "has_edge"):
                        is_dep = topology.has_edge(service, historical_service) or topology.has_edge(historical_service, service)
                    elif isinstance(topology, dict):
                        is_dep = historical_service in topology.get(service, []) or service in topology.get(historical_service, [])
                    if is_dep:
                        structural_score += 0.15

            # 2. Graph node-type overlap (similarity in failure characteristics)
            if graph is not None:
                current_types = {getattr(n, "type", "") for n in getattr(graph, "nodes", [])}
                historical_types = set(payload.get("anomalies_types") or [])
                if current_types and historical_types:
                    overlap = len(current_types.intersection(historical_types)) / len(current_types)
                    structural_score += overlap * 0.15

            # Add structural score to semantic score
            item.similarity_score = round(min(1.0, item.similarity_score + structural_score), 4)
            ranked_items.append(item)

        # Sort by updated similarity_score
        ranked_items.sort(key=lambda x: x.similarity_score, reverse=True)
        return ranked_items[:limit]


def _payload_to_text(payload: dict[str, Any]) -> str:
    """Convert payload fields to a single embedding text."""
    parts = []
    for key in ("title", "summary", "root_cause", "action", "outcome", "service", "description"):
        val = payload.get(key, "")
        if val:
            parts.append(str(val))
    return " ".join(parts) or str(payload)


_MEMORY_COLLECTIONS = {
    "incident_memory": "memory_incidents",
    "remediation_memory": "memory_remediation",
    "deployment_memory": "memory_deployments",
    "topology_memory": "memory_topology",
    "noisy_alert_memory": "memory_noisy_alerts",
    "escalation_memory": "memory_escalations",
}


class OperationalMemory:
    """
    Six-category operational memory for SentinelOps.

    Usage:
        mem = OperationalMemory()
        await mem.incident_memory.store("INC-001", {...})
        items = await mem.remediation_memory.recall("rollback payment-api after deployment")
    """

    def __init__(
        self,
        *,
        transport: httpx.BaseTransport | None = None,
        embedding_transport: httpx.BaseTransport | None = None,
    ) -> None:
        settings = get_settings()
        embedding_client = EmbeddingClient(transport=embedding_transport or transport)
        collection_manager = QdrantCollectionManager(
            base_url=settings.qdrant_url,
            transport=transport,
        )
        spec_size = embedding_client.dimensions

        for collection_name in _MEMORY_COLLECTIONS.values():
            collection_manager.ensure_collection(CollectionSpec(collection_name, spec_size))

        self.incident_memory = _MemoryStore(
            collection_name=_MEMORY_COLLECTIONS["incident_memory"],
            category="incident_memory",
            embedding_client=embedding_client,
            collection_manager=collection_manager,
        )
        self.remediation_memory = _MemoryStore(
            collection_name=_MEMORY_COLLECTIONS["remediation_memory"],
            category="remediation_memory",
            embedding_client=embedding_client,
            collection_manager=collection_manager,
        )
        self.deployment_memory = _MemoryStore(
            collection_name=_MEMORY_COLLECTIONS["deployment_memory"],
            category="deployment_memory",
            embedding_client=embedding_client,
            collection_manager=collection_manager,
        )
        self.topology_memory = _MemoryStore(
            collection_name=_MEMORY_COLLECTIONS["topology_memory"],
            category="topology_memory",
            embedding_client=embedding_client,
            collection_manager=collection_manager,
        )
        self.noisy_alert_memory = _MemoryStore(
            collection_name=_MEMORY_COLLECTIONS["noisy_alert_memory"],
            category="noisy_alert_memory",
            embedding_client=embedding_client,
            collection_manager=collection_manager,
        )
        self.escalation_memory = _MemoryStore(
            collection_name=_MEMORY_COLLECTIONS["escalation_memory"],
            category="escalation_memory",
            embedding_client=embedding_client,
            collection_manager=collection_manager,
        )

    @property
    def categories(self) -> list[str]:
        return list(_MEMORY_COLLECTIONS.keys())
