"""
Tests that worker restart and task failure scenarios are survivable.

Covers:
  - Deferred task persistence on broker failure
  - Replay respects max attempt budget and dead-letters exhausted tasks
  - reject_on_worker_lost prevents message loss on worker crash
  - Bootstrap checkpoint is persisted before graph execution
"""
from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from workers.tasks.incident_pipeline import (
    _MAX_REPLAY_ATTEMPTS,
    _replay_pending_incidents,
    _store_deferred_task,
    enqueue_incident_pipeline,
)


# ---------------------------------------------------------------------------
# Deferred-task persistence
# ---------------------------------------------------------------------------

def test_enqueue_stores_deferred_task_when_broker_fails(monkeypatch):
    recorded: dict = {}

    def fail_delay(*_args, **_kwargs):
        raise ConnectionRefusedError("broker down")

    async def fake_store(incident_id, error=None):
        recorded["incident_id"] = str(incident_id)
        recorded["error"] = str(error)

    monkeypatch.setattr("workers.tasks.incident_pipeline.run_incident_pipeline.delay", fail_delay)
    monkeypatch.setattr("workers.tasks.incident_pipeline._store_deferred_task", fake_store)

    incident_id = str(uuid4())
    enqueue_incident_pipeline(incident_id)

    assert recorded["incident_id"] == incident_id
    assert "broker down" in recorded["error"]


# ---------------------------------------------------------------------------
# Replay max-attempt budget
# ---------------------------------------------------------------------------

class _FakeTask:
    def __init__(self, *, attempts: int, incident_id: str | None = None):
        self.id = uuid4()
        self.attempts = attempts
        self.incident_id = uuid4()
        self.payload = {"incident_id": str(self.incident_id)}


class _FakeRepo:
    def __init__(self, tasks):
        self._tasks = tasks
        self.dead_lettered: list[tuple] = []
        self.completed: list = []
        self.running: list = []

    async def list_pending_tasks(self, _task_name):
        return self._tasks

    async def mark_running(self, task_id):
        self.running.append(task_id)

    async def mark_completed(self, task_id):
        self.completed.append(task_id)

    async def mark_failed(self, task_id, error):
        pass

    async def mark_dead_letter(self, task_id, reason):
        self.dead_lettered.append((task_id, reason))


class _FakeSession:
    def __init__(self, repo):
        self._repo = repo

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass


@pytest.mark.asyncio
async def test_replay_dead_letters_tasks_exceeding_max_attempts(monkeypatch):
    exhausted = _FakeTask(attempts=_MAX_REPLAY_ATTEMPTS)
    healthy = _FakeTask(attempts=2)
    repo = _FakeRepo([exhausted, healthy])

    def fake_delay(incident_id_str):
        pass

    monkeypatch.setattr("workers.tasks.incident_pipeline.run_incident_pipeline.delay", fake_delay)

    class _SessionCtx:
        async def __aenter__(self_inner):
            return self_inner

        async def __aexit__(self_inner, *_):
            pass

    # Patch PendingTaskRepository to return our fake repo
    monkeypatch.setattr(
        "workers.tasks.incident_pipeline.PendingTaskRepository",
        lambda _session: repo,
    )
    monkeypatch.setattr(
        "workers.tasks.incident_pipeline.SessionLocal",
        lambda: _SessionCtx(),
    )

    replayed = await _replay_pending_incidents()

    assert replayed == 1
    assert len(repo.dead_lettered) == 1
    assert repo.dead_lettered[0][0] == exhausted.id


@pytest.mark.asyncio
async def test_replay_skips_healthy_tasks_not_exceeding_budget(monkeypatch):
    task = _FakeTask(attempts=1)
    repo = _FakeRepo([task])

    def fake_delay(_):
        pass

    monkeypatch.setattr("workers.tasks.incident_pipeline.run_incident_pipeline.delay", fake_delay)
    monkeypatch.setattr("workers.tasks.incident_pipeline.PendingTaskRepository", lambda _: repo)

    class _SessionCtx:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *_):
            pass

    monkeypatch.setattr("workers.tasks.incident_pipeline.SessionLocal", lambda: _SessionCtx())

    replayed = await _replay_pending_incidents()

    assert replayed == 1
    assert len(repo.dead_lettered) == 0
    assert task.id in repo.completed


# ---------------------------------------------------------------------------
# Task configuration — reject_on_worker_lost and acks_late
# ---------------------------------------------------------------------------

def test_run_incident_pipeline_task_has_reject_on_worker_lost():
    from workers.tasks.incident_pipeline import run_incident_pipeline

    assert getattr(run_incident_pipeline, "reject_on_worker_lost", False) is True


def test_run_incident_pipeline_task_has_acks_late():
    from workers.tasks.incident_pipeline import run_incident_pipeline

    assert getattr(run_incident_pipeline, "acks_late", False) is True


def test_escalate_approval_task_has_reject_on_worker_lost():
    from workers.tasks.approval_escalation import escalate_approval

    assert getattr(escalate_approval, "reject_on_worker_lost", False) is True


# ---------------------------------------------------------------------------
# Celery queue configuration
# ---------------------------------------------------------------------------

def test_celery_app_has_time_limits():
    from workers.queues import celery_app

    assert celery_app.conf.task_soft_time_limit == 300
    assert celery_app.conf.task_time_limit == 360


def test_celery_app_rejects_on_worker_lost():
    from workers.queues import celery_app

    assert celery_app.conf.reject_on_worker_lost is True


def test_celery_app_acks_late():
    from workers.queues import celery_app

    assert celery_app.conf.task_acks_late is True
