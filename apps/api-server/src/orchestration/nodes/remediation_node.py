from agents.remediation_agent import build_remediation_plan
from db.repositories.incident_repo import IncidentRepository
from db.session import SessionLocal


async def remediation_node(state: dict, session=None) -> dict:
    if session is None:
        async with SessionLocal() as owned_session:
            return await remediation_node(state, owned_session)
    repository = IncidentRepository(session)
    incident = await repository.get_with_context(state["incident_id"])
    if incident is None:
        return {"errors": [f"Incident {state['incident_id']} not found"]}
    result = await build_remediation_plan(incident, db_session=session)
    await repository.replace_remediation_actions(
        incident.id,
        [step.model_dump(mode="json") for step in result.steps],
    )
    return {
        "remediation_plan": result.model_dump(mode="json"),
        "completed_nodes": ["remediation"],
    }
