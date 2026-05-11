from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from core.config import get_settings


@dataclass(frozen=True)
class CollectionSpec:
    name: str
    vector_size: int
    distance: str = "Cosine"


class QdrantCollectionManager:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.qdrant_url).rstrip("/")
        self._sync_client = httpx.Client(base_url=self.base_url, timeout=timeout, transport=transport)
        self._async_client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout, transport=transport)

    def close(self) -> None:
        self._sync_client.close()

    async def aclose(self) -> None:
        await self._async_client.aclose()

    def ensure_collection(self, spec: CollectionSpec) -> bool:
        payload = {"vectors": {"size": spec.vector_size, "distance": spec.distance}}
        try:
            response = self._sync_client.put(f"/collections/{spec.name}", json=payload)
            response.raise_for_status()
            return True
        except httpx.HTTPError:
            return False

    async def ensure_collection_async(self, spec: CollectionSpec) -> bool:
        payload = {"vectors": {"size": spec.vector_size, "distance": spec.distance}}
        try:
            response = await self._async_client.put(f"/collections/{spec.name}", json=payload)
            response.raise_for_status()
            return True
        except httpx.HTTPError:
            return False

    def upsert_points(self, collection: str, points: list[dict[str, Any]]) -> bool:
        try:
            response = self._sync_client.put(
                f"/collections/{collection}/points?wait=true",
                json={"points": points},
            )
            response.raise_for_status()
            return True
        except httpx.HTTPError:
            return False

    async def upsert_points_async(self, collection: str, points: list[dict[str, Any]]) -> bool:
        try:
            response = await self._async_client.put(
                f"/collections/{collection}/points?wait=true",
                json={"points": points},
            )
            response.raise_for_status()
            return True
        except httpx.HTTPError:
            return False

    def search(self, collection: str, vector: list[float], limit: int = 3) -> list[dict[str, Any]]:
        payload = {"vector": vector, "limit": limit, "with_payload": True}
        try:
            response = self._sync_client.post(f"/collections/{collection}/points/search", json=payload)
            response.raise_for_status()
            return response.json().get("result", [])
        except httpx.HTTPError:
            return []

    async def search_async(self, collection: str, vector: list[float], limit: int = 3) -> list[dict[str, Any]]:
        payload = {"vector": vector, "limit": limit, "with_payload": True}
        try:
            response = await self._async_client.post(f"/collections/{collection}/points/search", json=payload)
            response.raise_for_status()
            return response.json().get("result", [])
        except httpx.HTTPError:
            return []
