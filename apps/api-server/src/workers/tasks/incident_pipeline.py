from __future__ import annotations

from uuid import UUID

import structlog

from db.session import SessionLocal
from db.repositories.task_repo import PendingTaskRepository
from workers.async_utils import run_async
from workers.queues import celery_app

logger = structlog.get_logger(__name__)

_MAX_REPLAY_ATTEMPTS = 5
_STALE_REPLAY_AFTER_SECONDS = 300


@celery_app.task(
    name="workers.tasks.run_incident_pipeline",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
    reject_on_worker_lost=True,
    acks_late=True,
)
def run_incident_pipeline(incident_id: str) -> None:
    run_async(_run_incident_pipeline(UUID(incident_id)))


async def _run_incident_pipeline(incident_id: UUID) -> None:
    from orchestration.graphs.main_graph import build_main_graph

    async with SessionLocal() as session:
        task_repo = PendingTaskRepository(session)
        await task_repo.mark_running_by_incident(incident_id, "workers.tasks.run_incident_pipeline")

    graph = build_main_graph()
    try:
        result = await graph.ainvoke({"incident_id": str(incident_id)})
        logger.info(
            "incident_pipeline_completed",
            incident_id=str(incident_id),
            status=result.get("status") if isinstance(result, dict) else "unknown",
            operating_mode=result.get("operating_mode") if isinstance(result, dict) else "unknown",
            fallback_activated=result.get("fallback_activated") if isinstance(result, dict) else False,
        )
        async with SessionLocal() as session:
            await PendingTaskRepository(session).mark_completed_by_incident(
                incident_id, "workers.tasks.run_incident_pipeline"
            )
    except Exception as exc:
        logger.error(
            "incident_pipeline_failed",
            incident_id=str(incident_id),
            error=str(exc),
            error_type=type(exc).__name__,
        )
        async with SessionLocal() as session:
            await PendingTaskRepository(session).mark_failed_by_incident(
                incident_id,
                "workers.tasks.run_incident_pipeline",
                str(exc),
            )
        await _store_deferred_task(incident_id, exc)
        raise


async def _store_deferred_task(incident_id: UUID, error: Exception | None = None) -> None:
    async with SessionLocal() as session:
        await PendingTaskRepository(session).create_pending_task(
            incident_id=incident_id,
            task_name="workers.tasks.run_incident_pipeline",
            payload={"incident_id": str(incident_id)},
            status="pending",
            last_error=str(error) if error is not None else None,
        )


async def enqueue_incident_pipeline(incident_id: str) -> None:
    incident_uuid = UUID(incident_id)
    try:
        await _store_deferred_task(
            incident_uuid,
            None,
        )
        run_incident_pipeline.delay(incident_id)
    except Exception as exc:  # noqa: BLE001
        await _store_deferred_task(incident_uuid, exc)


@celery_app.task(name="workers.tasks.replay_pending_incidents")
def replay_pending_incidents() -> int:
    return run_async(_replay_pending_incidents())


async def _replay_pending_incidents() -> int:
    async with SessionLocal() as session:
        repository = PendingTaskRepository(session)
        pending = await repository.list_recoverable_tasks(
            "workers.tasks.run_incident_pipeline",
            stale_after_seconds=_STALE_REPLAY_AFTER_SECONDS,
        )
        replayed = 0
        for task in pending:
            if task.attempts >= _MAX_REPLAY_ATTEMPTS:
                await repository.mark_dead_letter(task.id, "exceeded max replay attempts")
                logger.warning(
                    "task_moved_to_dead_letter",
                    task_id=str(task.id),
                    incident_id=str(task.incident_id),
                    attempts=task.attempts,
                )
                continue
            try:
                run_incident_pipeline.delay(task.payload["incident_id"])
                replayed += 1
            except Exception as exc:  # noqa: BLE001
                await repository.mark_failed(task.id, str(exc))
        return replayed
