"""
EmbeddingClient: semantic embedding with multi-provider fallback.

This module replaces the Phase <41 hash-based EmbeddingClient with a real
semantic embedding implementation backed by SemanticEmbeddingClient.

The public API (embed_text, dimensions) is backward compatible with all
existing callers in RetrievalOrchestrator, PatternSearcher, and
IncidentHistorySearcher.
"""

from __future__ import annotations

import hashlib
import math

import httpx
from retrieval.embeddings.semantic_embedding_client import SemanticEmbeddingClient


class EmbeddingClient:
    """
    Backward-compatible wrapper around SemanticEmbeddingClient.

    Provides sync embed_text and dimensions property to existing callers
    while delegating all embedding logic to SemanticEmbeddingClient.
    """

    def __init__(
        self,
        *,
        dimensions: int | None = None,
        model: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = SemanticEmbeddingClient(model=model, transport=transport)
        self._dimensions_override = dimensions

    def _legacy_hash_embed(self, text: str) -> list[float]:
        if not text:
            return [0.0] * self.dimensions
        vector = [0.0] * self.dimensions
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode()).digest()
            index = digest[0] % self.dimensions
            weight = (digest[1] / 255.0) + 0.5
            vector[index] += weight
        norm = math.sqrt(sum(value * value for value in vector))
        if norm < 1e-9:
            return vector
        return [value / norm for value in vector]

    def _resize(self, vector: list[float]) -> list[float]:
        target = self.dimensions
        if len(vector) == target:
            return vector
        if len(vector) > target:
            return vector[:target]
        return vector + [0.0] * (target - len(vector))

    @property
    def dimensions(self) -> int:
        return self._dimensions_override or self._client.dimensions

    @property
    def active_model(self) -> str:
        return self._client.active_model

    def embed_text(self, text: str) -> list[float]:
        if self._dimensions_override is not None:
            return self._legacy_hash_embed(text)
        return self._resize(self._client.embed_text(text))

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if self._dimensions_override is not None:
            return [self._legacy_hash_embed(text) for text in texts]
        return [self._resize(vector) for vector in self._client.embed_batch(texts)]

    async def embed_text_async(self, text: str) -> list[float]:
        if self._dimensions_override is not None:
            return self._legacy_hash_embed(text)
        return self._resize(await self._client.embed_text_async(text))

    async def embed_batch_async(self, texts: list[str]) -> list[list[float]]:
        if self._dimensions_override is not None:
            return [self._legacy_hash_embed(text) for text in texts]
        return [self._resize(vector) for vector in await self._client.embed_batch_async(texts)]
