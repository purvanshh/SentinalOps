from agents.metrics_agent import analyze_metrics
from db.repositories.incident_repo import IncidentRepository
from db.session import SessionLocal


async def metrics_node(state: dict, session=None) -> dict:
    if session is None:
        async with SessionLocal() as owned_session:
            return await metrics_node(state, owned_session)
    repository = IncidentRepository(session)
    incident = await repository.get(state["incident_id"])
    if incident is None:
        return {"errors": [f"Incident {state['incident_id']} not found"]}
    result = await analyze_metrics(incident, db_session=session)
    return {"metrics_summary": result.model_dump(mode="json"), "completed_nodes": ["metrics"]}
