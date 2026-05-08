from agents.metrics_agent import analyze_metrics
from db.repositories.incident_repo import IncidentRepository


async def metrics_node(state: dict, session) -> dict:
    repository = IncidentRepository(session)
    incident = await repository.get(state["incident_id"])
    if incident is None:
        return {}
    result = await analyze_metrics(incident, db_session=session)
    return {"metrics": result.model_dump(mode="json")}
