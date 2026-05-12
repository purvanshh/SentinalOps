"""
Tests that queue configuration, dead-letter handling, and task durability
are correctly set up.

Covers:
  - DLQ / dead-letter status for exhausted tasks
  - Celery serialization restricted to JSON
  - Broker-outage fallback stores task durably
  - mark_dead_letter transitions task status correctly
  - list_dead_letter_tasks returns only dead-letter entries
"""
from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from workers.tasks.incident_pipeline import _MAX_REPLAY_ATTEMPTS, enqueue_incident_pipeline


# ---------------------------------------------------------------------------
# Celery configuration assertions
# ---------------------------------------------------------------------------

def test_celery_serializer_is_json():
    from workers.queues import celery_app

    assert celery_app.conf.task_serializer == "json"
    assert celery_app.conf.result_serializer == "json"
    assert "json" in celery_app.conf.accept_content


def test_celery_prefetch_multiplier_is_one():
    from workers.queues import celery_app

    assert celery_app.conf.worker_prefetch_multiplier == 1


def test_incident_pipeline_queue_routing():
    from workers.queues import celery_app

    routes = celery_app.conf.task_routes
    assert routes["workers.tasks.run_incident_pipeline"]["queue"] == "incidents"
    assert routes["workers.tasks.replay_pending_incidents"]["queue"] == "incidents"
    assert routes["workers.tasks.escalate_approval"]["queue"] == "approvals"


# ---------------------------------------------------------------------------
# Dead-letter repository operations
# ---------------------------------------------------------------------------

class _FakePendingTask:
    def __init__(self, status="pending", attempts=0):
        self.id = uuid4()
        self.incident_id = uuid4()
        self.status = status
        self.attempts = attempts
        self.last_error = None
        self.payload = {"incident_id": str(self.incident_id)}


class _FakeSession:
    def __init__(self):
        self._store: dict = {}

    async def get(self, _model, task_id):
        return self._store.get(task_id)

    async def commit(self):
        pass

    async def refresh(self, obj):
        pass

    async def execute(self, _stmt):
        return _FakeResult([v for v in self._store.values() if v.status == "dead_letter"])


class _FakeResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items


@pytest.mark.asyncio
async def test_mark_dead_letter_sets_status():
    from db.repositories.task_repo import PendingTaskRepository

    session = _FakeSession()
    task = _FakePendingTask()
    session._store[task.id] = task

    repo = PendingTaskRepository(session)
    result = await repo.mark_dead_letter(task.id, "exceeded max retries")

    assert result.status == "dead_letter"
    assert "exceeded max retries" in result.last_error


@pytest.mark.asyncio
async def test_mark_dead_letter_returns_none_for_missing_task():
    from db.repositories.task_repo import PendingTaskRepository

    session = _FakeSession()
    repo = PendingTaskRepository(session)
    result = await repo.mark_dead_letter(uuid4(), "some reason")

    assert result is None


@pytest.mark.asyncio
async def test_list_dead_letter_tasks_returns_only_dead_letter():
    from db.repositories.task_repo import PendingTaskRepository

    session = _FakeSession()
    dead = _FakePendingTask(status="dead_letter")
    alive = _FakePendingTask(status="pending")
    session._store[dead.id] = dead
    session._store[alive.id] = alive

    repo = PendingTaskRepository(session)
    results = await repo.list_dead_letter_tasks()

    assert len(results) == 1
    assert results[0].id == dead.id


# ---------------------------------------------------------------------------
# MAX_REPLAY_ATTEMPTS constant
# ---------------------------------------------------------------------------

def test_max_replay_attempts_is_bounded():
    """Budget must be finite and reasonable — not zero, not unbounded."""
    assert 1 <= _MAX_REPLAY_ATTEMPTS <= 20


# ---------------------------------------------------------------------------
# Broker outage — task is persisted durably
# ---------------------------------------------------------------------------

def test_broker_outage_persists_task_to_pending_store(monkeypatch):
    stored: dict = {}

    def fail_delay(_incident_id):
        raise ConnectionRefusedError("Redis unavailable")

    async def capture_store(incident_id, error=None):
        stored["incident_id"] = str(incident_id)
        stored["error"] = str(error)

    monkeypatch.setattr(
        "workers.tasks.incident_pipeline.run_incident_pipeline.delay", fail_delay
    )
    monkeypatch.setattr(
        "workers.tasks.incident_pipeline._store_deferred_task", capture_store
    )

    incident_id = str(uuid4())
    enqueue_incident_pipeline(incident_id)

    assert stored.get("incident_id") == incident_id
    assert stored.get("error") is not None
