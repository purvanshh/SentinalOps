"""
Semantic embedding client with multi-provider fallback.

Provider hierarchy:
  1. Primary — OpenAI-compatible /v1/embeddings (text-embedding-3-small, 1536d)
  2. Fallback — Ollama /api/embeddings (bge-small-en-v1.5, 384d)
  3. Emergency — hash-based with padded dimensions (no network required)

The emergency fallback is honest: it produces a semantically meaningless vector
but does NOT crash the pipeline. Callers should monitor `active_model` to detect
when a degraded embedding is in use.
"""

from __future__ import annotations

import hashlib
import math
from typing import Any

import httpx
from core.config import get_settings

_MODEL_DIMENSIONS: dict[str, int] = {
    "text-embedding-3-small": 1536,
    "text-embedding-ada-002": 1536,
    "bge-small-en-v1.5": 384,
    "nomic-embed-text": 768,
}

_EMERGENCY_FALLBACK = "hash-fallback"


class SemanticEmbeddingClient:
    """Multi-provider semantic embedding client with caching and graceful fallback."""

    def __init__(
        self,
        *,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        fallback_model: str | None = None,
        fallback_base_url: str | None = None,
        transport: httpx.BaseTransport | None = None,
        max_cache_size: int = 512,
    ) -> None:
        settings = get_settings()
        self.model = model or settings.embedding_model
        self.fallback_model = fallback_model or settings.embedding_fallback_model
        self._base_url = (base_url or settings.llm_base_url).rstrip("/")
        self._api_key = api_key or settings.llm_api_key
        self._fallback_base_url = (fallback_base_url or settings.llm_local_base_url).rstrip("/")
        self._transport = transport
        self._cache: dict[str, list[float]] = {}
        self._max_cache_size = max_cache_size
        self._active_model: str = self.model

    @property
    def dimensions(self) -> int:
        return _MODEL_DIMENSIONS.get(self.model, 1536)

    @property
    def active_model(self) -> str:
        return self._active_model

    # ── cache ──────────────────────────────────────────────────────────────────

    def _cache_key(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:24]

    def _cache_get(self, text: str) -> list[float] | None:
        return self._cache.get(self._cache_key(text))

    def _cache_put(self, text: str, vector: list[float]) -> None:
        if len(self._cache) >= self._max_cache_size:
            oldest = next(iter(self._cache))
            del self._cache[oldest]
        self._cache[self._cache_key(text)] = vector

    # ── normalisation ──────────────────────────────────────────────────────────

    def _normalize(self, vector: list[float]) -> list[float]:
        norm = math.sqrt(sum(x * x for x in vector))
        if norm < 1e-9:
            return vector
        return [x / norm for x in vector]

    def _pad_or_truncate(self, vector: list[float], size: int) -> list[float]:
        if len(vector) >= size:
            return vector[:size]
        return vector + [0.0] * (size - len(vector))

    # ── hash-based emergency fallback ──────────────────────────────────────────

    def _hash_embed(self, text: str) -> list[float]:
        """Hash-based fallback that produces a vector of declared dimensions."""
        vector = [0.0] * self.dimensions
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode()).digest()
            idx = digest[0] % self.dimensions
            weight = (digest[1] / 255.0) + 0.5
            vector[idx] += weight
        norm = math.sqrt(sum(x * x for x in vector))
        if norm < 1e-9:
            return vector
        return [x / norm for x in vector]

    # ── sync providers ──────────────────────────────────────────────────────────

    def _sync_client(self, base_url: str) -> httpx.Client:
        return httpx.Client(base_url=base_url, timeout=10.0, transport=self._transport)

    def _try_openai_sync(self, text: str) -> list[float] | None:
        try:
            with self._sync_client(self._base_url) as client:
                resp = client.post(
                    "/v1/embeddings",
                    json={"input": text, "model": self.model},
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
                resp.raise_for_status()
                vec = resp.json()["data"][0]["embedding"]
                self._active_model = self.model
                return self._normalize(vec)
        except Exception:  # noqa: BLE001
            return None

    def _try_ollama_sync(self, text: str) -> list[float] | None:
        try:
            with self._sync_client(self._fallback_base_url) as client:
                resp = client.post(
                    "/api/embeddings",
                    json={"model": self.fallback_model, "prompt": text},
                )
                resp.raise_for_status()
                vec = resp.json()["embedding"]
                vec = self._pad_or_truncate(vec, self.dimensions)
                self._active_model = self.fallback_model
                return self._normalize(vec)
        except Exception:  # noqa: BLE001
            return None

    def embed_text(self, text: str) -> list[float]:
        cached = self._cache_get(text)
        if cached is not None:
            return cached
        vec = self._try_openai_sync(text) or self._try_ollama_sync(text)
        if vec is None:
            self._active_model = _EMERGENCY_FALLBACK
            vec = self._hash_embed(text)
        self._cache_put(text, vec)
        return vec

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(t) for t in texts]

    # ── async providers ────────────────────────────────────────────────────────

    def _async_client(self, base_url: str) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=base_url, timeout=10.0, transport=self._transport)

    async def _try_openai_async(self, text: str) -> list[float] | None:
        try:
            async with self._async_client(self._base_url) as client:
                resp = await client.post(
                    "/v1/embeddings",
                    json={"input": text, "model": self.model},
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
                resp.raise_for_status()
                vec = resp.json()["data"][0]["embedding"]
                self._active_model = self.model
                return self._normalize(vec)
        except Exception:  # noqa: BLE001
            return None

    async def _try_ollama_async(self, text: str) -> list[float] | None:
        try:
            async with self._async_client(self._fallback_base_url) as client:
                resp = await client.post(
                    "/api/embeddings",
                    json={"model": self.fallback_model, "prompt": text},
                )
                resp.raise_for_status()
                vec = resp.json()["embedding"]
                vec = self._pad_or_truncate(vec, self.dimensions)
                self._active_model = self.fallback_model
                return self._normalize(vec)
        except Exception:  # noqa: BLE001
            return None

    async def embed_text_async(self, text: str) -> list[float]:
        cached = self._cache_get(text)
        if cached is not None:
            return cached
        vec = await self._try_openai_async(text)
        if vec is None:
            vec = await self._try_ollama_async(text)
        if vec is None:
            self._active_model = _EMERGENCY_FALLBACK
            vec = self._hash_embed(text)
        self._cache_put(text, vec)
        return vec

    async def embed_batch_async(self, texts: list[str]) -> list[list[float]]:
        results: list[list[float]] = []
        for text in texts:
            results.append(await self.embed_text_async(text))
        return results

    def cache_stats(self) -> dict[str, Any]:
        return {
            "size": len(self._cache),
            "capacity": self._max_cache_size,
            "active_model": self._active_model,
            "declared_model": self.model,
            "dimensions": self.dimensions,
        }
