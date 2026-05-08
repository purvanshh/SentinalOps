import asyncio
from uuid import UUID

from agents.deployment_agent import analyze_deployments
from agents.logs_agent import analyze_logs
from agents.metrics_agent import analyze_metrics
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
        classification = await classify_incident(incident, db_session=session)

        if classification.confidence >= 0.6:
            await asyncio.gather(
                _run_metrics_agent(incident_id),
                _run_logs_agent(incident_id),
                _run_deployment_agent(incident_id),
            )


async def _run_metrics_agent(incident_id: UUID) -> None:
    async with SessionLocal() as session:
        repository = IncidentRepository(session)
        incident = await repository.get(incident_id)
        if incident is None:
            return
        await analyze_metrics(incident, db_session=session)


async def _run_logs_agent(incident_id: UUID) -> None:
    async with SessionLocal() as session:
        repository = IncidentRepository(session)
        incident = await repository.get(incident_id)
        if incident is None:
            return
        await analyze_logs(incident, db_session=session)


async def _run_deployment_agent(incident_id: UUID) -> None:
    async with SessionLocal() as session:
        repository = IncidentRepository(session)
        incident = await repository.get(incident_id)
        if incident is None:
            return
        await analyze_deployments(incident, db_session=session)


def enqueue_incident_pipeline(incident_id: str) -> None:
    try:
        run_incident_pipeline.delay(incident_id)
    except Exception:
        # Keep webhook intake resilient even if the broker is unavailable.
        pass
