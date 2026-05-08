from typing import Any

import httpx

from core.config import get_settings
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
        self.collection_name = collection_name
        self.embedding_client = EmbeddingClient()
        self._client = httpx.AsyncClient(base_url=self.base_url, transport=transport, timeout=10.0)

    async def close(self) -> None:
        await self._client.aclose()

    async def search_similar_incidents(self, text: str, limit: int = 3) -> list[dict[str, Any]]:
        vector = self.embedding_client.embed_text(text)
        payload = {
            "vector": vector,
            "limit": limit,
            "with_payload": True,
        }
        try:
            response = await self._client.post(
                f"/collections/{self.collection_name}/points/search",
                json=payload,
            )
            response.raise_for_status()
            results = response.json().get("result", [])
        except httpx.HTTPError:
            return []

        return [
            {
                "score": item.get("score"),
                **(item.get("payload") or {}),
            }
            for item in results
        ]
