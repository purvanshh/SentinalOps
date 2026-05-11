from typing import Any

import httpx

from core.config import get_settings
from retrieval.embeddings.collection_manager import CollectionSpec, QdrantCollectionManager
from retrieval.embeddings.embedding_client import EmbeddingClient


class IncidentHistorySearcher:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        collection_name: str = "past_incidents",
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.qdrant_url).rstrip("/")
        self.collection_name = collection_name or settings.qdrant_incident_collection
        self.embedding_client = EmbeddingClient()
        self.collection_manager = QdrantCollectionManager(base_url=self.base_url, transport=transport)
        self.collection_manager.ensure_collection(
            CollectionSpec(self.collection_name, self.embedding_client.dimensions)
        )

    async def close(self) -> None:
        await self.collection_manager.aclose()

    async def search_similar_incidents(self, text: str, limit: int = 3) -> list[dict[str, Any]]:
        vector = self.embedding_client.embed_text(text)
        results = await self.collection_manager.search_async(self.collection_name, vector, limit=limit)

        return [
            {
                "score": item.get("score"),
                **(item.get("payload") or {}),
            }
            for item in results
        ]

    async def upsert_incident(
        self,
        *,
        incident_id: str,
        title: str,
        summary: str,
        root_cause: str,
    ) -> bool:
        vector = self.embedding_client.embed_text(f"{title}\n{summary}\n{root_cause}")
        return await self.collection_manager.upsert_points_async(
            self.collection_name,
            [
                {
                    "id": incident_id,
                    "vector": vector,
                    "payload": {
                        "incident_id": incident_id,
                        "title": title,
                        "summary": summary,
                        "root_cause": root_cause,
                    },
                }
            ],
        )
