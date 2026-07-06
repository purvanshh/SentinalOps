from __future__ import annotations

import asyncio
from uuid import uuid4

from workers.tasks.incident_pipeline import enqueue_incident_pipeline


def test_enqueue_incident_pipeline_persists_pending_task_on_broker_failure(monkeypatch) -> None:
    recorded = {}

    def fake_delay(_incident_id: str) -> None:
        raise RuntimeError("broker unavailable")

    async def fake_store(incident_id, error=None):
        recorded["incident_id"] = str(incident_id)
        recorded["error"] = str(error)

    monkeypatch.setattr("workers.tasks.incident_pipeline.run_incident_pipeline.delay", fake_delay)
    monkeypatch.setattr("workers.tasks.incident_pipeline._store_deferred_task", fake_store)

    incident_id = str(uuid4())
    asyncio.run(enqueue_incident_pipeline(incident_id))

    assert recorded["incident_id"] == incident_id
    assert "broker unavailable" in recorded["error"]
