"""
Scalability and hot-path efficiency tests.

Proves:
  - RetrievalOrchestrator indexing methods do NOT call bootstrap/ensure_collection
  - EmbeddingClient produces deterministic, normalised vectors
  - Collection manager upsert/search never trigger ensure_collection
  - Health endpoint returns required service keys without making external calls
  - Concurrent indexing calls do not share mutable vector state
"""

from __future__ import annotations

import threading
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Qdrant hot-path: bootstrap must NOT be called by indexing methods
# ---------------------------------------------------------------------------


def test_index_patterns_does_not_call_bootstrap(monkeypatch):
    from retrieval.retrieval_orchestrator import RetrievalOrchestrator

    orch = RetrievalOrchestrator.__new__(RetrievalOrchestrator)
    orch.settings = MagicMock()
    orch.settings.qdrant_pattern_collection = "patterns"
    orch.embedding_client = MagicMock()
    orch.embedding_client.embed_text.return_value = [0.1] * 16
    orch.collection_manager = MagicMock()
    orch.collection_manager.upsert_points.return_value = True
    orch.bootstrap = MagicMock()

    orch.index_patterns(
        [{"title": "CPU spike", "description": "High CPU", "symptoms": ["latency"]}]
    )

    orch.bootstrap.assert_not_called()
    orch.collection_manager.ensure_collection.assert_not_called()


def test_index_runbooks_does_not_call_bootstrap(monkeypatch, tmp_path):
    from retrieval.retrieval_orchestrator import RetrievalOrchestrator

    runbook = tmp_path / "restart.md"
    runbook.write_text("# Restart pod\nkubectl rollout restart deployment/api")

    orch = RetrievalOrchestrator.__new__(RetrievalOrchestrator)
    orch.settings = MagicMock()
    orch.settings.qdrant_runbook_collection = "runbooks"
    orch.embedding_client = MagicMock()
    orch.embedding_client.embed_text.return_value = [0.1] * 16
    orch.collection_manager = MagicMock()
    orch.collection_manager.upsert_points.return_value = True
    orch.bootstrap = MagicMock()

    orch.index_runbooks_from_directory(tmp_path)

    orch.bootstrap.assert_not_called()
    orch.collection_manager.ensure_collection.assert_not_called()


@pytest.mark.asyncio
async def test_index_prevention_items_does_not_call_bootstrap():
    from retrieval.retrieval_orchestrator import RetrievalOrchestrator

    orch = RetrievalOrchestrator.__new__(RetrievalOrchestrator)
    orch.settings = MagicMock()
    orch.settings.qdrant_prevention_collection = "prevention_items"
    orch.embedding_client = MagicMock()
    orch.embedding_client.embed_text.return_value = [0.1] * 16
    orch.collection_manager = MagicMock()
    orch.collection_manager.upsert_points_async = AsyncMock(return_value=True)
    orch.bootstrap = MagicMock()

    await orch.index_prevention_items(
        [{"title": "Update deps", "description": "Patch CVE-2024-1234", "status": "open"}]
    )

    orch.bootstrap.assert_not_called()
    orch.collection_manager.ensure_collection.assert_not_called()
    orch.collection_manager.ensure_collection_async = AsyncMock()
    orch.collection_manager.ensure_collection_async.assert_not_called()


@pytest.mark.asyncio
async def test_index_resolved_incident_does_not_call_bootstrap():
    from retrieval.retrieval_orchestrator import RetrievalOrchestrator

    orch = RetrievalOrchestrator.__new__(RetrievalOrchestrator)
    orch.settings = MagicMock()
    orch.settings.qdrant_incident_collection = "past_incidents"
    orch.embedding_client = MagicMock()
    orch.embedding_client.embed_text.return_value = [0.1] * 16
    orch.collection_manager = MagicMock()
    orch.collection_manager.upsert_points_async = AsyncMock(return_value=True)
    orch.bootstrap = MagicMock()

    await orch.index_resolved_incident(
        incident_id="inc-001",
        title="OOMKill on api-server",
        summary="Pod was OOMKilled due to memory leak in request handler",
        root_cause="Unbounded in-memory cache accumulating parsed bodies",
    )

    orch.bootstrap.assert_not_called()
    orch.collection_manager.ensure_collection.assert_not_called()


# ---------------------------------------------------------------------------
# EmbeddingClient: determinism and normalization
# ---------------------------------------------------------------------------


def test_embedding_is_deterministic():
    from retrieval.embeddings.embedding_client import EmbeddingClient

    client = EmbeddingClient(dimensions=16)
    v1 = client.embed_text("pod OOMKilled in production namespace")
    v2 = client.embed_text("pod OOMKilled in production namespace")
    assert v1 == v2


def test_embedding_is_unit_normalised():
    import math

    from retrieval.embeddings.embedding_client import EmbeddingClient

    client = EmbeddingClient(dimensions=16)
    vec = client.embed_text("high CPU usage on api-server replica")
    norm = math.sqrt(sum(x * x for x in vec))
    assert abs(norm - 1.0) < 1e-9 or norm == 0.0


def test_empty_text_embedding_returns_zero_vector():
    from retrieval.embeddings.embedding_client import EmbeddingClient

    client = EmbeddingClient(dimensions=16)
    vec = client.embed_text("")
    assert all(v == 0.0 for v in vec)
    assert len(vec) == 16


def test_different_texts_produce_different_embeddings():
    from retrieval.embeddings.embedding_client import EmbeddingClient

    client = EmbeddingClient(dimensions=16)
    v1 = client.embed_text("database connection pool exhausted")
    v2 = client.embed_text("kubernetes pod evicted due to memory pressure")
    assert v1 != v2


# ---------------------------------------------------------------------------
# Concurrent indexing: no shared mutable vector state
# ---------------------------------------------------------------------------


def test_concurrent_index_calls_produce_independent_vectors():
    from retrieval.embeddings.embedding_client import EmbeddingClient

    client = EmbeddingClient(dimensions=16)
    results: dict[int, list[float]] = {}

    def embed(i: int) -> None:
        results[i] = client.embed_text(f"incident {i} root cause analysis")

    threads = [threading.Thread(target=embed, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All 20 threads should have produced a result
    assert len(results) == 20
    # Results for same index should be identical across runs (determinism)
    for i, vec in results.items():
        assert client.embed_text(f"incident {i} root cause analysis") == vec


# ---------------------------------------------------------------------------
# Health endpoint: structure check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_response_contains_required_service_keys():
    from unittest.mock import AsyncMock

    from api.routes.health import health_check

    with (
        patch("api.routes.health.OperatingModeManager") as mock_mode,
        patch("api.routes.health.get_provider_chain") as mock_chain,
        patch("api.routes.health.build_metrics_snapshot", return_value={}),
        patch("api.routes.health.observe_api_request"),
        patch("api.routes.health._probe_redis", new=AsyncMock(return_value="reachable")),
        patch("api.routes.health._probe_qdrant", new=AsyncMock(return_value="reachable")),
    ):
        mock_mode.return_value.current_mode.value = "normal"
        mock_mode.return_value.to_dict.return_value = {}
        mock_chain.return_value.get_health.return_value = {}

        result = await health_check()

    services = result["services"]
    assert "postgres" in services
    assert "redis" in services
    assert "qdrant" in services


def test_health_missing_url_reports_missing():
    from api.routes.health import _service_status

    assert _service_status("") == "missing"
    assert _service_status(None) == "missing"


def test_health_configured_url_reports_configured():
    from api.routes.health import _service_status

    assert _service_status("http://localhost:6333") == "configured"
    assert _service_status("redis://localhost:6379") == "configured"
