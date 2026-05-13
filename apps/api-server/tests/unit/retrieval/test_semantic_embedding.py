"""
Phase 42 semantic embedding client tests.

Proves:
  1. SemanticEmbeddingClient uses real OpenAI-compatible API when available.
  2. Falls back to Ollama when primary provider fails.
  3. Falls back to hash-based when all providers fail (emergency fallback).
  4. Returns normalized, dimension-correct vectors in all cases.
  5. Caches embeddings to avoid redundant API calls.
  6. EmbeddingClient backward-compat wrapper preserves the embed_text interface.
  D. Embedding fallback — primary unavailable → fallback activates.
"""
from __future__ import annotations

import json
import math

import httpx
import pytest

from retrieval.embeddings.embedding_client import EmbeddingClient
from retrieval.embeddings.semantic_embedding_client import (
    SemanticEmbeddingClient,
    _EMERGENCY_FALLBACK,
)


def _mock_openai_response(dims: int = 8) -> dict:
    vec = [1.0 / math.sqrt(dims)] * dims
    return {"data": [{"embedding": vec, "index": 0}], "model": "text-embedding-3-small"}


def _mock_ollama_response(dims: int = 8) -> dict:
    vec = [1.0 / math.sqrt(dims)] * dims
    return {"embedding": vec}


# ─── Primary OpenAI provider ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_semantic_client_uses_openai_when_available() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if "/v1/embeddings" in str(request.url):
            return httpx.Response(200, json=_mock_openai_response(8))
        return httpx.Response(404)

    client = SemanticEmbeddingClient(
        model="text-embedding-3-small",
        transport=httpx.MockTransport(handler),
    )
    vec = await client.embed_text_async("postgres latency spike")

    assert any("/v1/embeddings" in url for url in calls), "Primary OpenAI endpoint not called"
    assert client.active_model == "text-embedding-3-small"
    assert len(vec) == 8


@pytest.mark.asyncio
async def test_semantic_client_falls_back_to_ollama_when_primary_fails() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if "/v1/embeddings" in str(request.url):
            return httpx.Response(500)
        if "/api/embeddings" in str(request.url):
            return httpx.Response(200, json=_mock_ollama_response(8))
        return httpx.Response(404)

    client = SemanticEmbeddingClient(
        model="text-embedding-3-small",
        fallback_model="bge-small-en-v1.5",
        transport=httpx.MockTransport(handler),
    )
    vec = await client.embed_text_async("database connection refused")

    assert any("/api/embeddings" in url for url in calls), "Ollama fallback endpoint not called"
    assert client.active_model == "bge-small-en-v1.5"
    # Ollama result is padded/truncated to declared model dimensions (1536 for text-embedding-3-small)
    assert len(vec) == client.dimensions


def test_semantic_client_uses_emergency_hash_fallback_when_all_providers_fail() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    client = SemanticEmbeddingClient(
        model="text-embedding-3-small",
        transport=httpx.MockTransport(handler),
    )
    vec = client.embed_text("payment gateway timeout")

    assert client.active_model == _EMERGENCY_FALLBACK
    assert len(vec) == client.dimensions
    assert len(vec) == 1536


# ─── Normalization ────────────────────────────────────────────────────────────


def test_semantic_client_returns_normalized_vector() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "/v1/embeddings" in str(request.url):
            return httpx.Response(200, json={"data": [{"embedding": [3.0, 4.0], "index": 0}]})
        return httpx.Response(500)

    client = SemanticEmbeddingClient(transport=httpx.MockTransport(handler))
    vec = client.embed_text("latency spike")
    norm = math.sqrt(sum(x * x for x in vec))
    assert abs(norm - 1.0) < 1e-6, f"Vector not normalized: norm={norm}"


def test_emergency_hash_fallback_always_produces_declared_dimensions() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    client = SemanticEmbeddingClient(
        model="text-embedding-3-small",
        transport=httpx.MockTransport(handler),
    )
    assert client.dimensions == 1536
    vec = client.embed_text("any incident text here")
    assert len(vec) == 1536, f"Expected 1536 dimensions, got {len(vec)}"


def test_bge_fallback_dimensions_correct() -> None:
    client = SemanticEmbeddingClient(model="bge-small-en-v1.5", transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    assert client.dimensions == 384
    vec = client.embed_text("test")
    assert len(vec) == 384


# ─── Caching ──────────────────────────────────────────────────────────────────


def test_semantic_client_caches_embeddings() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json={"data": [{"embedding": [1.0, 0.0], "index": 0}]})

    client = SemanticEmbeddingClient(transport=httpx.MockTransport(handler))
    text = "cache test incident description"

    _ = client.embed_text(text)
    _ = client.embed_text(text)
    _ = client.embed_text(text)

    assert call_count == 1, f"Expected 1 API call (cached), got {call_count}"


def test_semantic_client_cache_stats_reflect_entries() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"embedding": [1.0, 0.0], "index": 0}]})

    client = SemanticEmbeddingClient(transport=httpx.MockTransport(handler))
    client.embed_text("first incident")
    client.embed_text("second incident")

    stats = client.cache_stats()
    assert stats["size"] == 2
    assert stats["capacity"] == 512
    assert "active_model" in stats
    assert "dimensions" in stats


# ─── Dimension validation ──────────────────────────────────────────────────────


def test_semantic_client_pads_ollama_short_vector_to_declared_dims() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "/v1/embeddings" in str(request.url):
            return httpx.Response(500)
        # Ollama returns 4d but model declares 1536d
        return httpx.Response(200, json={"embedding": [0.5, 0.5, 0.5, 0.5]})

    client = SemanticEmbeddingClient(
        model="text-embedding-3-small",
        fallback_model="bge-small-en-v1.5",
        transport=httpx.MockTransport(handler),
    )
    vec = client.embed_text("test padding")
    assert len(vec) == 1536, f"Expected 1536 after padding, got {len(vec)}"


# ─── Backward-compatible EmbeddingClient wrapper ──────────────────────────────


def test_embedding_client_wrapper_exposes_embed_text() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "/v1/embeddings" in str(request.url):
            return httpx.Response(200, json={"data": [{"embedding": [0.6, 0.8], "index": 0}]})
        return httpx.Response(500)

    client = EmbeddingClient(transport=httpx.MockTransport(handler))
    vec = client.embed_text("latency spike on payment-api")
    assert len(vec) > 0
    norm = math.sqrt(sum(x * x for x in vec))
    assert abs(norm - 1.0) < 1e-6


def test_embedding_client_wrapper_dimensions_match_model() -> None:
    client = EmbeddingClient(transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    assert client.dimensions == 1536  # text-embedding-3-small default


@pytest.mark.asyncio
async def test_embedding_client_wrapper_async_embed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"embedding": [1.0, 0.0], "index": 0}]})

    client = EmbeddingClient(transport=httpx.MockTransport(handler))
    vec = await client.embed_text_async("async embedding test")
    assert len(vec) > 0


def test_embedding_client_embed_batch_returns_list_of_vectors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"embedding": [0.6, 0.8], "index": 0}]})

    client = EmbeddingClient(transport=httpx.MockTransport(handler))
    results = client.embed_batch(["incident A", "incident B", "incident C"])
    assert len(results) == 3
    for vec in results:
        assert len(vec) > 0
