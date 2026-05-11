from __future__ import annotations

import asyncio
from uuid import UUID

from db.session import SessionLocal
from db.repositories.task_repo import PendingTaskRepository
from workers.queues import celery_app


@celery_app.task(
    name="workers.tasks.run_incident_pipeline",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def run_incident_pipeline(incident_id: str) -> None:
    asyncio.run(_run_incident_pipeline(UUID(incident_id)))


async def _run_incident_pipeline(incident_id: UUID) -> None:
    from orchestration.graphs.main_graph import build_main_graph

    graph = build_main_graph()
    await graph.ainvoke({"incident_id": str(incident_id)})


async def _store_deferred_task(incident_id: UUID, error: Exception | None = None) -> None:
    async with SessionLocal() as session:
        await PendingTaskRepository(session).create_pending_task(
            incident_id=incident_id,
            task_name="workers.tasks.run_incident_pipeline",
            payload={"incident_id": str(incident_id)},
            status="pending",
            last_error=str(error) if error is not None else None,
        )


def enqueue_incident_pipeline(incident_id: str) -> None:
    incident_uuid = UUID(incident_id)
    try:
        run_incident_pipeline.delay(incident_id)
    except Exception as exc:  # noqa: BLE001
        asyncio.run(_store_deferred_task(incident_uuid, exc))


@celery_app.task(name="workers.tasks.replay_pending_incidents")
def replay_pending_incidents() -> int:
    return asyncio.run(_replay_pending_incidents())


async def _replay_pending_incidents() -> int:
    async with SessionLocal() as session:
        repository = PendingTaskRepository(session)
        pending = await repository.list_pending_tasks("workers.tasks.run_incident_pipeline")
        replayed = 0
        for task in pending:
            await repository.mark_running(task.id)
            try:
                run_incident_pipeline.delay(task.payload["incident_id"])
                await repository.mark_completed(task.id)
                replayed += 1
            except Exception as exc:  # noqa: BLE001
                await repository.mark_failed(task.id, str(exc))
        return replayed
