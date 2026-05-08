from agents.remediation_agent import build_remediation_plan
from db.repositories.incident_repo import IncidentRepository


async def remediation_node(state: dict, session) -> dict:
    repository = IncidentRepository(session)
    incident = await repository.get_with_context(state["incident_id"])
    if incident is None:
        return {}
    result = await build_remediation_plan(incident, db_session=session)
    await repository.replace_remediation_actions(
        incident.id,
        [step.model_dump(mode="json") for step in result.steps],
    )
    return {"remediation": result.model_dump(mode="json")}
