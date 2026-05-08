from agents.router_agent import classify_incident
from db.repositories.incident_repo import IncidentRepository


async def router_node(state: dict, session) -> dict:
    repository = IncidentRepository(session)
    incident = await repository.get(state["incident_id"])
    if incident is None:
        return {}
    result = await classify_incident(incident, db_session=session)
    return {"router": result.model_dump(mode="json"), "status": "classified"}
