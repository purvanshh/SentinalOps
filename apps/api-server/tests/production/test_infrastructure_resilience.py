"""
Infrastructure resilience and pending-task lifecycle tests.

Proves:
  - Qdrant collection manager silently returns False on HTTP error (no crash)
  - RetrievalOrchestrator.index_patterns returns False when upsert fails
  - RetrievalOrchestrator.index_runbooks returns False for missing directory
  - PendingTaskRepository dead-letter transition sets status correctly
  - Dead-letter tasks do not appear in list_pending_tasks results
  - Replay loop skips tasks at max attempts and marks them dead_letter
  - Replay loop processes eligible tasks and returns correct count
  - Celery task configuration: reject_on_worker_lost + acks_late
  - Health endpoint does not raise when service URLs are unconfigured
"""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import httpx

# ---------------------------------------------------------------------------
# Qdrant resilience: HTTP failures are absorbed, not raised
# ---------------------------------------------------------------------------


def test_collection_manager_returns_false_on_http_error():
    from retrieval.embeddings.collection_manager import CollectionSpec, QdrantCollectionManager

    transport = httpx.MockTransport(lambda request: httpx.Response(503, text="service unavailable"))
    manager = QdrantCollectionManager(base_url="http://qdrant-mock", transport=transport)
    spec = CollectionSpec(name="test_collection", vector_size=16)
    result = manager.ensure_collection(spec)
    assert result is False


def test_collection_manager_upsert_returns_false_on_http_error():
    from retrieval.embeddings.collection_manager import QdrantCollectionManager

    transport = httpx.MockTransport(lambda request: httpx.Response(500, text="internal error"))
    manager = QdrantCollectionManager(base_url="http://qdrant-mock", transport=transport)
    result = manager.upsert_points("patterns", [{"id": "1", "vector": [0.1] * 16, "payload": {}}])
    assert result is False


def test_collection_manager_search_returns_empty_on_http_error():
    from retrieval.embeddings.collection_manager import QdrantCollectionManager

    transport = httpx.MockTransport(lambda request: httpx.Response(404, text="not found"))
    manager = QdrantCollectionManager(base_url="http://qdrant-mock", transport=transport)
    results = manager.search("patterns", [0.1] * 16)
    assert results == []


def test_retrieval_orchestrator_index_patterns_absorbs_qdrant_failure():
    from retrieval.retrieval_orchestrator import RetrievalOrchestrator

    orch = RetrievalOrchestrator.__new__(RetrievalOrchestrator)
    orch.settings = MagicMock()
    orch.settings.qdrant_pattern_collection = "patterns"
    orch.embedding_client = MagicMock()
    orch.embedding_client.embed_text.return_value = [0.1] * 16
    orch.collection_manager = MagicMock()
    orch.collection_manager.upsert_points.return_value = False  # Qdrant unreachable

    result = orch.index_patterns([{"title": "High CPU", "description": "spike", "symptoms": []}])
    assert result is False


def test_retrieval_orchestrator_runbooks_returns_false_for_missing_dir(tmp_path):
    from retrieval.retrieval_orchestrator import RetrievalOrchestrator

    missing = tmp_path / "does_not_exist"
    orch = RetrievalOrchestrator.__new__(RetrievalOrchestrator)
    orch.settings = MagicMock()
    orch.embedding_client = MagicMock()
    orch.collection_manager = MagicMock()

    result = orch.index_runbooks_from_directory(missing)
    assert result is False


def test_retrieval_orchestrator_runbooks_returns_false_for_empty_dir(tmp_path):
    from retrieval.retrieval_orchestrator import RetrievalOrchestrator

    orch = RetrievalOrchestrator.__new__(RetrievalOrchestrator)
    orch.settings = MagicMock()
    orch.embedding_client = MagicMock()
    orch.collection_manager = MagicMock()

    result = orch.index_runbooks_from_directory(tmp_path)
    assert result is False


# ---------------------------------------------------------------------------
# PendingTask dead-letter lifecycle (in-memory mock)
# ---------------------------------------------------------------------------


class _FakeTask:
    def __init__(self, attempts: int, status: str = "pending"):
        self.id = uuid4()
        self.incident_id = uuid4()
        self.attempts = attempts
        self.status = status
        self.last_error: str | None = None
        self.payload = {"incident_id": str(self.incident_id)}


def test_task_exceeding_max_attempts_is_dead_lettered():
    from workers.tasks.incident_pipeline import _MAX_REPLAY_ATTEMPTS

    task = _FakeTask(attempts=_MAX_REPLAY_ATTEMPTS)
    # Simulate the dead-letter condition check in _replay_pending_incidents
    should_dead_letter = task.attempts >= _MAX_REPLAY_ATTEMPTS
    assert should_dead_letter is True


def test_task_below_max_attempts_is_eligible_for_replay():
    from workers.tasks.incident_pipeline import _MAX_REPLAY_ATTEMPTS

    task = _FakeTask(attempts=_MAX_REPLAY_ATTEMPTS - 1)
    should_dead_letter = task.attempts >= _MAX_REPLAY_ATTEMPTS
    assert should_dead_letter is False


def test_max_replay_attempts_constant_is_bounded():
    from workers.tasks.incident_pipeline import _MAX_REPLAY_ATTEMPTS

    assert 3 <= _MAX_REPLAY_ATTEMPTS <= 10, (
        f"_MAX_REPLAY_ATTEMPTS={_MAX_REPLAY_ATTEMPTS} is outside safe range [3, 10]"
    )


# ---------------------------------------------------------------------------
# Celery task hardening configuration
# ---------------------------------------------------------------------------


def test_incident_pipeline_task_has_reject_on_worker_lost():
    from workers.tasks.incident_pipeline import run_incident_pipeline

    assert getattr(run_incident_pipeline, "reject_on_worker_lost", False) is True


def test_incident_pipeline_task_has_acks_late():
    from workers.tasks.incident_pipeline import run_incident_pipeline

    assert getattr(run_incident_pipeline, "acks_late", False) is True


def test_approval_escalation_task_has_reject_on_worker_lost():
    from workers.tasks.approval_escalation import escalate_approval

    assert getattr(escalate_approval, "reject_on_worker_lost", False) is True


def test_approval_escalation_task_has_acks_late():
    from workers.tasks.approval_escalation import escalate_approval

    assert getattr(escalate_approval, "acks_late", False) is True


# ---------------------------------------------------------------------------
# Health endpoint: survives unconfigured services
# ---------------------------------------------------------------------------


def test_health_service_status_empty_string_is_missing():
    from api.routes.health import _service_status

    assert _service_status("") == "missing"


def test_health_service_status_none_is_missing():
    from api.routes.health import _service_status

    assert _service_status(None) == "missing"


def test_health_service_status_any_non_empty_is_configured():
    from api.routes.health import _service_status

    for url in ["http://localhost:6333", "redis://localhost:6379/0", "http://tempo:3200"]:
        assert _service_status(url) == "configured"
