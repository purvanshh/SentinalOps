import asyncio
from uuid import UUID

from agents.router_agent import classify_incident
from db.repositories.incident_repo import IncidentRepository
from db.session import SessionLocal
from workers.queues import celery_app


@celery_app.task(name="workers.tasks.run_incident_pipeline")
def run_incident_pipeline(incident_id: str) -> None:
    asyncio.run(_run_incident_pipeline(UUID(incident_id)))


async def _run_incident_pipeline(incident_id: UUID) -> None:
    async with SessionLocal() as session:
        repository = IncidentRepository(session)
        incident = await repository.get(incident_id)
        if incident is None:
            return

        incident.status = "investigating"
        await session.commit()
        await session.refresh(incident)
        await classify_incident(incident, db_session=session)


def enqueue_incident_pipeline(incident_id: str) -> None:
    try:
        run_incident_pipeline.delay(incident_id)
    except Exception:
        # Keep webhook intake resilient even if the broker is unavailable.
        pass
