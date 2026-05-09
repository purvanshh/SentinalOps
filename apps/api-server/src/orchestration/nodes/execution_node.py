from db.repositories.incident_repo import IncidentRepository
from db.session import SessionLocal


async def execution_node(state: dict, session=None) -> dict:
    if session is None:
        async with SessionLocal() as owned_session:
            return await execution_node(state, owned_session)
    repository = IncidentRepository(session)
    incident = await repository.get_with_context(state["incident_id"])
    if incident is None:
        return {"errors": [f"Incident {state['incident_id']} not found"]}
    approved = state.get("approval", {}).get("approved", False)
    note = state.get("approval", {}).get("note", "")
    approved_by = state.get("approval", {}).get("approved_by")
    for action in incident.remediation_actions:
        action.approved = approved
        action.approved_by = approved_by
        action.details = {**(action.details or {}), "approval_note": note}
        if approved:
            action.executed = True
            action.status = "executed"
        else:
            action.status = "rejected"
    incident.status = "resolved" if approved else "approval_rejected"
    await session.commit()
    return {
        "execution": {
            "approved": approved,
            "executed_actions": [action.action for action in incident.remediation_actions if action.executed],
        },
        "status": incident.status,
        "approved_actions": [action.action for action in incident.remediation_actions if action.executed],
        "completed_nodes": ["execution"],
    }
