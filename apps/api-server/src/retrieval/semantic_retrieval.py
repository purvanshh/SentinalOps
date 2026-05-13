"""
Semantic incident retrieval with provenance and operational grounding.

SemanticIncidentRetriever wraps IncidentHistorySearcher and enriches every
retrieved item with:
  - similarity_score: cosine similarity from Qdrant
  - retrieval_reason: human-readable explanation of why this incident matched
  - matched_dimensions: which operational domains matched (service, error type, etc.)
  - embedding_model: which model produced the query vector
  - retrieved_at: ISO-8601 UTC timestamp

This makes retrieval transparent to operators and enables hallucination
suppression: the root cause agent can cite the retrieval provenance rather than
inventing historical context.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from retrieval.incident_history.searcher import IncidentHistorySearcher


_OPERATIONAL_DIMENSIONS = [
    "latency",
    "error_rate",
    "database",
    "deployment",
    "memory",
    "cpu",
    "network",
    "timeout",
    "connection",
    "authentication",
    "throughput",
    "queue",
    "cascade",
    "rollback",
    "regression",
]


def _extract_matched_dimensions(query: str, payload: dict[str, Any]) -> list[str]:
    """Identify which operational domains appear in both query and retrieved incident."""
    query_lower = query.lower()
    combined = " ".join([
        payload.get("title", ""),
        payload.get("summary", ""),
        payload.get("root_cause", ""),
    ]).lower()

    return [
        dim for dim in _OPERATIONAL_DIMENSIONS
        if dim in query_lower and dim in combined
    ]


def _build_retrieval_reason(score: float, matched: list[str], payload: dict[str, Any]) -> str:
    service = payload.get("service", "")
    title = payload.get("title", "")
    if score >= 0.90:
        strength = "highly similar"
    elif score >= 0.75:
        strength = "semantically similar"
    else:
        strength = "weakly related"

    parts = [f"{strength} incident"]
    if title:
        parts.append(f'"{title}"')
    if matched:
        parts.append(f"shared dimensions: {', '.join(matched[:3])}")
    if service:
        parts.append(f"affecting {service}")
    return "; ".join(parts)


class SemanticIncidentRetriever:
    """
    Retrieves semantically similar historical incidents with full provenance.

    Every retrieved item carries structured provenance so operators understand
    WHY a historical incident was retrieved and HOW confident the match is.
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        collection_name: str = "past_incidents",
        transport: httpx.BaseTransport | None = None,
        embedding_transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._searcher = IncidentHistorySearcher(
            base_url=base_url,
            collection_name=collection_name,
            transport=transport,
            embedding_transport=embedding_transport,
        )

    async def close(self) -> None:
        await self._searcher.close()

    @property
    def embedding_model(self) -> str:
        return self._searcher.embedding_client.active_model

    async def retrieve(
        self,
        query: str,
        *,
        limit: int = 5,
        min_score: float = 0.0,
    ) -> list[dict[str, Any]]:
        """
        Retrieve semantically similar incidents with provenance metadata.

        Args:
            query: Natural-language description of the current incident.
            limit: Maximum number of results to return.
            min_score: Minimum cosine similarity to include (0.0 = no filter).

        Returns:
            List of dicts, each containing the incident payload plus:
              similarity_score, retrieval_reason, matched_dimensions,
              embedding_model, retrieved_at, meets_threshold.
        """
        raw = await self._searcher.search_similar_incidents(query, limit=limit * 2)
        retrieved_at = datetime.now(UTC).isoformat()
        model = self.embedding_model

        results: list[dict[str, Any]] = []
        for item in raw:
            score = float(item.get("score") or 0.0)
            if score < min_score:
                continue
            matched = _extract_matched_dimensions(query, item)
            results.append({
                **item,
                "similarity_score": round(score, 4),
                "retrieval_reason": _build_retrieval_reason(score, matched, item),
                "matched_dimensions": matched,
                "embedding_model": model,
                "retrieved_at": retrieved_at,
                "meets_threshold": score >= min_score,
            })

        results.sort(key=lambda r: r["similarity_score"], reverse=True)
        return results[:limit]

    async def index_incident(
        self,
        *,
        incident_id: str,
        title: str,
        summary: str,
        root_cause: str,
        service: str = "",
    ) -> bool:
        """Index a resolved incident into the semantic memory store."""
        return await self._searcher.upsert_incident(
            incident_id=incident_id,
            title=title,
            summary=summary,
            root_cause=root_cause,
        )
