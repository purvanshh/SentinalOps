from agents.rootcause_agent import analyze_root_cause
from db.repositories.incident_repo import IncidentRepository
from db.session import SessionLocal


async def rootcause_node(state: dict, session=None) -> dict:
    if session is None:
        async with SessionLocal() as owned_session:
            return await rootcause_node(state, owned_session)
    repository = IncidentRepository(session)
    incident = await repository.get_with_context(state["incident_id"])
    if incident is None:
        return {"errors": [f"Incident {state['incident_id']} not found"]}
    result = await analyze_root_cause(incident, db_session=session)
    return {
        "root_cause": result.model_dump(mode="json"),
        "hypotheses": [hypothesis.model_dump(mode="json") for hypothesis in result.hypotheses],
        "completed_nodes": ["root_cause_analysis"],
    }
