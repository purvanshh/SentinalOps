from agents.rootcause_agent import analyze_root_cause
from db.repositories.incident_repo import IncidentRepository


async def rootcause_node(state: dict, session) -> dict:
    repository = IncidentRepository(session)
    incident = await repository.get_with_context(state["incident_id"])
    if incident is None:
        return {}
    result = await analyze_root_cause(incident, db_session=session)
    return {"root_cause": result.model_dump(mode="json")}
