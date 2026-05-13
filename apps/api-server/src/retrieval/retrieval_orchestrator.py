"""
RetrievalOrchestrator: vector search and incident history indexing.

Collection bootstrap (ensure_collection) must be called ONCE at application
startup via RetrievalOrchestrator().bootstrap(). Individual indexing methods
(index_patterns, index_runbooks_from_directory, index_prevention_items,
index_resolved_incident) no longer call bootstrap() themselves — doing so
would issue an HTTP request to Qdrant on every write, adding unnecessary
latency to hot paths.

See apps/api-server/src/main.py lifespan for the startup call.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from core.config import get_settings
from retrieval.embeddings.collection_manager import CollectionSpec, QdrantCollectionManager
from retrieval.embeddings.embedding_client import EmbeddingClient


class RetrievalOrchestrator:
    def __init__(self) -> None:
        settings = get_settings()
        self.settings = settings
        self.embedding_client = EmbeddingClient()
        self.collection_manager = QdrantCollectionManager(base_url=settings.qdrant_url)

    def bootstrap(self) -> None:
        """Create all required Qdrant collections if they do not exist.

        Call this ONCE at application startup — not from indexing hot paths.
        """
        dimensions = self.embedding_client.dimensions
        specs = [
            CollectionSpec(self.settings.qdrant_pattern_collection, dimensions),
            CollectionSpec(self.settings.qdrant_incident_collection, dimensions),
            CollectionSpec(self.settings.qdrant_runbook_collection, dimensions),
            CollectionSpec(self.settings.qdrant_prevention_collection, dimensions),
        ]
        for spec in specs:
            self.collection_manager.ensure_collection(spec)

    def _point(
        self, payload: dict[str, Any], text: str, *, point_id: str | None = None
    ) -> dict[str, Any]:
        return {
            "id": point_id or str(uuid.uuid4()),
            "vector": self.embedding_client.embed_text(text),
            "payload": payload,
        }

    def index_patterns(self, patterns: list[dict[str, Any]]) -> bool:
        points = [
            self._point(
                {
                    "title": pattern.get("title", ""),
                    "description": pattern.get("description", ""),
                    "symptoms": pattern.get("symptoms", []),
                },
                " ".join(
                    [
                        pattern.get("title", ""),
                        pattern.get("description", ""),
                        " ".join(pattern.get("symptoms", [])),
                    ]
                ),
            )
            for pattern in patterns
        ]
        return self.collection_manager.upsert_points(
            self.settings.qdrant_pattern_collection, points
        )

    def index_runbooks_from_directory(self, path: str | Path) -> bool:
        directory = Path(path)
        if not directory.is_absolute():
            directory = Path.cwd() / directory
        if not directory.exists():
            return False
        points = []
        for file_path in directory.rglob("*.md"):
            content = file_path.read_text()
            points.append(
                self._point(
                    {
                        "title": file_path.stem,
                        "path": str(file_path),
                        "content": content,
                    },
                    f"{file_path.stem}\n{content}",
                )
            )
        if not points:
            return False
        return self.collection_manager.upsert_points(
            self.settings.qdrant_runbook_collection, points
        )

    async def index_prevention_items(self, items: list[dict[str, Any]]) -> bool:
        points = [
            self._point(
                {
                    "title": item.get("title", ""),
                    "description": item.get("description", ""),
                    "status": item.get("status", "open"),
                },
                f"{item.get('title', '')}\n{item.get('description', '')}",
            )
            for item in items
        ]
        if not points:
            return False
        return await self.collection_manager.upsert_points_async(
            self.settings.qdrant_prevention_collection, points
        )

    async def index_resolved_incident(
        self,
        *,
        incident_id: str,
        title: str,
        summary: str,
        root_cause: str,
    ) -> bool:
        point = self._point(
            {
                "incident_id": incident_id,
                "title": title,
                "summary": summary,
                "root_cause": root_cause,
            },
            f"{title}\n{summary}\n{root_cause}",
            point_id=incident_id,
        )
        return await self.collection_manager.upsert_points_async(
            self.settings.qdrant_incident_collection,
            [point],
        )

    async def search_prevention_items(self, text: str, limit: int = 3) -> list[dict[str, Any]]:
        vector = self.embedding_client.embed_text(text)
        results = await self.collection_manager.search_async(
            self.settings.qdrant_prevention_collection,
            vector,
            limit=limit,
        )
        return [{"score": item.get("score"), **(item.get("payload") or {})} for item in results]

    async def search_runbooks(self, text: str, limit: int = 3) -> list[dict[str, Any]]:
        vector = self.embedding_client.embed_text(text)
        results = await self.collection_manager.search_async(
            self.settings.qdrant_runbook_collection,
            vector,
            limit=limit,
        )
        return [{"score": item.get("score"), **(item.get("payload") or {})} for item in results]

    def load_pattern_file(
        self, path: str | Path = "configs/development/patterns.json"
    ) -> list[dict[str, Any]]:
        file_path = Path(path)
        if not file_path.is_absolute():
            file_path = Path.cwd() / file_path
        if not file_path.exists():
            return []
        return json.loads(file_path.read_text())
