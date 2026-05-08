import json
from pathlib import Path

from core.config import get_settings
from retrieval.embeddings.embedding_client import EmbeddingClient


class PatternSearcher:
    def __init__(self, path: str | None = None) -> None:
        settings = get_settings()
        self.path = Path(path or "configs/development/patterns.json")
        if not self.path.is_absolute():
            self.path = Path.cwd() / self.path
        self.embedding_client = EmbeddingClient()
        self.patterns = json.loads(self.path.read_text()) if self.path.exists() else []

    def search(self, text: str, limit: int = 3) -> list[dict]:
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
            }
            for score, pattern in scored_patterns[:limit]
        ]
