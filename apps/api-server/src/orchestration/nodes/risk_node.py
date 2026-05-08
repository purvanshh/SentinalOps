from agents.risk_agent import assess_risk
from db.repositories.incident_repo import IncidentRepository


async def risk_node(state: dict, session) -> dict:
    repository = IncidentRepository(session)
    incident = await repository.get_with_context(state["incident_id"])
    if incident is None:
        return {}
    result = await assess_risk(incident, db_session=session)
    return {"risk": result.model_dump(mode="json")}
