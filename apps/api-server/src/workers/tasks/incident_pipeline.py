import asyncio
from uuid import UUID

from sqlalchemy import select

from db.models.incident import Incident
from db.session import SessionLocal
from workers.queues import celery_app


@celery_app.task(name="workers.tasks.run_incident_pipeline")
def run_incident_pipeline(incident_id: str) -> None:
    asyncio.run(_run_incident_pipeline(UUID(incident_id)))


async def _run_incident_pipeline(incident_id: UUID) -> None:
    async with SessionLocal() as session:
        result = await session.execute(select(Incident).where(Incident.id == incident_id))
        incident = result.scalar_one_or_none()
        if incident is None:
            return

        incident.status = "investigating"
        await session.commit()


def enqueue_incident_pipeline(incident_id: str) -> None:
    try:
        run_incident_pipeline.delay(incident_id)
    except Exception:
        # Keep webhook intake resilient even if the broker is unavailable.
        pass
