import json
from datetime import UTC, datetime
from pathlib import Path

from core.config import get_settings
from retrieval.embeddings.collection_manager import QdrantCollectionManager
from retrieval.embeddings.embedding_client import EmbeddingClient


class PatternSearcher:
    def __init__(self, path: str | None = None) -> None:
        settings = get_settings()
        self.collection_name = settings.qdrant_pattern_collection
        self.path = Path(path or "configs/development/patterns.json")
        if not self.path.is_absolute():
            self.path = Path.cwd() / self.path
        self.embedding_client = EmbeddingClient()
        self.collection_manager = QdrantCollectionManager(base_url=settings.qdrant_url)
        self.patterns = json.loads(self.path.read_text()) if self.path.exists() else []
        # ensure_collection is NOT called here. Collections are bootstrapped
        # once at startup via RetrievalOrchestrator().bootstrap() in main.py.
        # Calling ensure_collection per-search adds an HTTP round-trip to every
        # pattern lookup and is unnecessary when the collection already exists.

    def _build_provenance(self, score: float, source: str) -> dict:
        return {
            "similarity_score": round(score, 4),
            "embedding_model": self.embedding_client.active_model,
            "retrieved_at": datetime.now(UTC).isoformat(),
            "source": source,
            "grounding_status": (
                "grounded"
                if score >= 0.70
                else ("weakly_grounded" if score >= 0.45 else "ungrounded")
            ),
        }

    def _fallback_search(self, text: str, limit: int = 3) -> list[dict]:
        query_vector = self.embedding_client.embed_text(text)
        scored_patterns: list[tuple[float, dict]] = []
        for pattern in self.patterns:
            corpus = " ".join(
                [
                    pattern.get("title", ""),
                    pattern.get("description", ""),
                    " ".join(pattern.get("symptoms", [])),
                ]
            )
            pattern_vector = self.embedding_client.embed_text(corpus)
            score = sum(a * b for a, b in zip(query_vector, pattern_vector, strict=False))
            scored_patterns.append((score, pattern))
        scored_patterns.sort(key=lambda item: item[0], reverse=True)
        return [
            {
                **pattern,
                "match_score": round(score, 4),
                "provenance": self._build_provenance(score, "pattern_fallback"),
            }
            for score, pattern in scored_patterns[:limit]
        ]

    def search(self, text: str, limit: int = 3) -> list[dict]:
        query_vector = self.embedding_client.embed_text(text)
        results = self.collection_manager.search(self.collection_name, query_vector, limit=limit)
        if results:
            return [
                {
                    **(item.get("payload") or {}),
                    "match_score": round(item.get("score", 0.0), 4),
                    "provenance": self._build_provenance(
                        item.get("score", 0.0), "qdrant_pattern_collection"
                    ),
                }
                for item in results
            ]
        return self._fallback_search(text, limit=limit)
