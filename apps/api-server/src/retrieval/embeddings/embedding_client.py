"""
EmbeddingClient: semantic embedding with multi-provider fallback.

This module replaces the Phase <41 hash-based EmbeddingClient with a real
semantic embedding implementation backed by SemanticEmbeddingClient.

The public API (embed_text, dimensions) is backward compatible with all
existing callers in RetrievalOrchestrator, PatternSearcher, and
IncidentHistorySearcher.
"""
from __future__ import annotations

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
        model: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = SemanticEmbeddingClient(model=model, transport=transport)

    @property
    def dimensions(self) -> int:
        return self._client.dimensions

    @property
    def active_model(self) -> str:
        return self._client.active_model

    def embed_text(self, text: str) -> list[float]:
        return self._client.embed_text(text)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return self._client.embed_batch(texts)

    async def embed_text_async(self, text: str) -> list[float]:
        return await self._client.embed_text_async(text)

    async def embed_batch_async(self, texts: list[str]) -> list[list[float]]:
        return await self._client.embed_batch_async(texts)
