from agents.deployment_agent import analyze_deployments
from db.repositories.incident_repo import IncidentRepository


async def deployment_node(state: dict, session) -> dict:
    repository = IncidentRepository(session)
    incident = await repository.get(state["incident_id"])
    if incident is None:
        return {}
    result = await analyze_deployments(incident, db_session=session)
    return {"deployment": result.model_dump(mode="json")}
