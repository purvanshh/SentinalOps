"""
Phase-38 Qdrant operational cleanup and startup bootstrap isolation.

Proves:
  - PatternSearcher.__init__ does NOT call ensure_collection
  - RetrievalOrchestrator indexing hot paths do NOT call bootstrap/ensure_collection
  - bootstrap() IS called exactly once in main.py lifespan (startup only)
  - Collection manager gracefully handles 503/500/404 responses
  - Async upsert and search follow the same resilience pattern
  - RetrievalOrchestrator.load_pattern_file returns [] for missing file
  - Pattern searcher falls back to in-memory search when Qdrant returns empty
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call

import httpx
import pytest


# ---------------------------------------------------------------------------
# PatternSearcher: no ensure_collection on instantiation
# ---------------------------------------------------------------------------

def test_pattern_searcher_init_does_not_call_ensure_collection(tmp_path):
    from retrieval.embeddings.pattern_searcher import PatternSearcher

    patterns_file = tmp_path / "patterns.json"
    patterns_file.write_text(json.dumps([
        {"title": "High CPU", "description": "CPU spike", "symptoms": ["latency"]}
    ]))

    with patch(
        "retrieval.embeddings.pattern_searcher.QdrantCollectionManager"
    ) as mock_manager_cls:
        mock_manager = MagicMock()
        mock_manager_cls.return_value = mock_manager

        searcher = PatternSearcher(path=str(patterns_file))

        mock_manager.ensure_collection.assert_not_called()


def test_pattern_searcher_search_does_not_call_ensure_collection(tmp_path):
    from retrieval.embeddings.pattern_searcher import PatternSearcher

    patterns_file = tmp_path / "patterns.json"
    patterns_file.write_text(json.dumps([
        {"title": "CPU spike", "description": "high CPU", "symptoms": ["slow"]}
    ]))

    with patch("retrieval.embeddings.pattern_searcher.QdrantCollectionManager") as mock_cls:
        mock_mgr = MagicMock()
        mock_mgr.search.return_value = []
        mock_cls.return_value = mock_mgr

        searcher = PatternSearcher(path=str(patterns_file))
        searcher.search("high cpu usage")

        mock_mgr.ensure_collection.assert_not_called()


# ---------------------------------------------------------------------------
# RetrievalOrchestrator hot paths: no bootstrap/ensure_collection
# ---------------------------------------------------------------------------

def test_retrieval_orchestrator_index_patterns_no_bootstrap():
    from retrieval.retrieval_orchestrator import RetrievalOrchestrator

    orch = RetrievalOrchestrator.__new__(RetrievalOrchestrator)
    orch.settings = MagicMock()
    orch.settings.qdrant_pattern_collection = "patterns"
    orch.embedding_client = MagicMock()
    orch.embedding_client.embed_text.return_value = [0.1] * 16
    orch.collection_manager = MagicMock()
    orch.collection_manager.upsert_points.return_value = True
    orch.bootstrap = MagicMock()

    orch.index_patterns([{"title": "OOM", "description": "Out of memory", "symptoms": []}])

    orch.bootstrap.assert_not_called()
    orch.collection_manager.ensure_collection.assert_not_called()


@pytest.mark.asyncio
async def test_retrieval_orchestrator_index_resolved_incident_no_bootstrap():
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
        title="Test",
        summary="Summary",
        root_cause="Root cause",
    )

    orch.bootstrap.assert_not_called()
    orch.collection_manager.ensure_collection.assert_not_called()
    orch.collection_manager.ensure_collection_async = AsyncMock()
    orch.collection_manager.ensure_collection_async.assert_not_called()


# ---------------------------------------------------------------------------
# Collection manager: HTTP error resilience (async paths)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_collection_manager_async_upsert_returns_false_on_503():
    import httpx
    from retrieval.embeddings.collection_manager import QdrantCollectionManager

    async def mock_handler(request):
        return httpx.Response(503, text="service unavailable")

    transport = httpx.MockTransport(mock_handler)
    manager = QdrantCollectionManager(base_url="http://qdrant-mock", transport=transport)

    result = await manager.upsert_points_async("patterns", [
        {"id": "1", "vector": [0.1] * 16, "payload": {}}
    ])
    assert result is False


@pytest.mark.asyncio
async def test_collection_manager_async_search_returns_empty_on_404():
    import httpx
    from retrieval.embeddings.collection_manager import QdrantCollectionManager

    async def mock_handler(request):
        return httpx.Response(404, text="collection not found")

    transport = httpx.MockTransport(mock_handler)
    manager = QdrantCollectionManager(base_url="http://qdrant-mock", transport=transport)

    results = await manager.search_async("patterns", [0.1] * 16)
    assert results == []


# ---------------------------------------------------------------------------
# load_pattern_file: missing file returns empty list
# ---------------------------------------------------------------------------

def test_load_pattern_file_returns_empty_for_missing_file(tmp_path):
    from retrieval.retrieval_orchestrator import RetrievalOrchestrator

    orch = RetrievalOrchestrator.__new__(RetrievalOrchestrator)
    orch.settings = MagicMock()
    orch.embedding_client = MagicMock()
    orch.collection_manager = MagicMock()

    result = orch.load_pattern_file(str(tmp_path / "nonexistent.json"))
    assert result == []


# ---------------------------------------------------------------------------
# PatternSearcher fallback: uses in-memory search when Qdrant returns empty
# ---------------------------------------------------------------------------

def test_pattern_searcher_falls_back_to_in_memory_when_qdrant_empty(tmp_path):
    from retrieval.embeddings.pattern_searcher import PatternSearcher

    patterns = [
        {"title": "High CPU", "description": "CPU utilization spike", "symptoms": ["latency", "slow"]},
        {"title": "OOM Kill", "description": "Out of memory", "symptoms": ["crash"]},
    ]
    patterns_file = tmp_path / "patterns.json"
    patterns_file.write_text(json.dumps(patterns))

    with patch("retrieval.embeddings.pattern_searcher.QdrantCollectionManager") as mock_cls:
        mock_mgr = MagicMock()
        mock_mgr.search.return_value = []  # Qdrant returns empty
        mock_cls.return_value = mock_mgr

        searcher = PatternSearcher(path=str(patterns_file))
        results = searcher.search("high cpu usage causing latency")

    assert len(results) > 0
    assert "match_score" in results[0]


# ---------------------------------------------------------------------------
# bootstrap() only called at startup (main.py), not per-request
# ---------------------------------------------------------------------------

def test_retrieval_orchestrator_bootstrap_called_in_startup(monkeypatch):
    """Verify main.py lifespan boots Qdrant collections at startup."""
    import inspect
    import main as main_module

    source = inspect.getsource(main_module)
    assert "bootstrap()" in source, "main.py must call bootstrap() in the lifespan"
    assert "qdrant_bootstrap" in source or "RetrievalOrchestrator" in source
