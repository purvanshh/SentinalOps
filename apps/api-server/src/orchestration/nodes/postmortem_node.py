from agents.postmortem_agent import generate_postmortem
from db.repositories.incident_repo import IncidentRepository


async def postmortem_node(state: dict, session) -> dict:
    repository = IncidentRepository(session)
    incident = await repository.get_with_context(state["incident_id"])
    if incident is None:
        return {}
    result = await generate_postmortem(incident, db_session=session)
    return {"postmortem": result}
