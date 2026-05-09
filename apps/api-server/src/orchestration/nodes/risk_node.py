from agents.risk_agent import assess_risk
from db.repositories.incident_repo import IncidentRepository
from db.session import SessionLocal


async def risk_node(state: dict, session=None) -> dict:
    if session is None:
        async with SessionLocal() as owned_session:
            return await risk_node(state, owned_session)
    repository = IncidentRepository(session)
    incident = await repository.get_with_context(state["incident_id"])
    if incident is None:
        return {"errors": [f"Incident {state['incident_id']} not found"]}
    result = await assess_risk(incident, db_session=session)
    return {"risk_assessment": result.model_dump(mode="json"), "completed_nodes": ["risk"]}
