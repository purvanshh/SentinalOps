from agents.postmortem_agent import generate_postmortem
from db.repositories.incident_repo import IncidentRepository
from db.session import SessionLocal


async def postmortem_node(state: dict, session=None) -> dict:
    if session is None:
        async with SessionLocal() as owned_session:
            return await postmortem_node(state, owned_session)
    repository = IncidentRepository(session)
    incident = await repository.get_with_context(state["incident_id"])
    if incident is None:
        return {"errors": [f"Incident {state['incident_id']} not found"]}
    result = await generate_postmortem(incident, db_session=session)
    return {"postmortem": result, "status": "resolved", "completed_nodes": ["postmortem_report"]}
