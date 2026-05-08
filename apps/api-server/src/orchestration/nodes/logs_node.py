from agents.logs_agent import analyze_logs
from db.repositories.incident_repo import IncidentRepository


async def logs_node(state: dict, session) -> dict:
    repository = IncidentRepository(session)
    incident = await repository.get(state["incident_id"])
    if incident is None:
        return {}
    result = await analyze_logs(incident, db_session=session)
    return {"logs": result.model_dump(mode="json")}
