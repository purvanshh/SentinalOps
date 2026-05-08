from uuid import UUID

import asyncio

from orchestration.graphs.main_graph import build_main_graph
from workers.queues import celery_app


@celery_app.task(name="workers.tasks.run_incident_pipeline")
def run_incident_pipeline(incident_id: str) -> None:
    asyncio.run(_run_incident_pipeline(UUID(incident_id)))


async def _run_incident_pipeline(incident_id: UUID) -> None:
    graph = build_main_graph()
    await graph.ainvoke({"incident_id": str(incident_id)})


def enqueue_incident_pipeline(incident_id: str) -> None:
    try:
        run_incident_pipeline.delay(incident_id)
    except Exception:
        # Keep webhook intake resilient even if the broker is unavailable.
        pass
