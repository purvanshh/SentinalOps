from agents.router_agent import classify_incident
from db.repositories.incident_repo import IncidentRepository
from db.session import SessionLocal


async def router_node(state: dict, session=None) -> dict:
    if session is None:
        async with SessionLocal() as owned_session:
            return await router_node(state, owned_session)
    repository = IncidentRepository(session)
    incident = await repository.get(state["incident_id"])
    if incident is None:
        return {"errors": [f"Incident {state['incident_id']} not found"], "status": "failed"}
    result = await classify_incident(incident, db_session=session)
    status = "classified" if result.confidence >= 0.6 else "needs_triage"
    return {
        "classification": result.model_dump(mode="json"),
        "status": status,
        "completed_nodes": ["router"],
        "remaining_steps": max(int(state.get("remaining_steps", 1)) - 1, 0),
    }
