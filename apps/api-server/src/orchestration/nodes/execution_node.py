from db.repositories.incident_repo import IncidentRepository


async def execution_node(state: dict, session) -> dict:
    repository = IncidentRepository(session)
    incident = await repository.get_with_context(state["incident_id"])
    if incident is None:
        return {}
    approved = state.get("approval", {}).get("approved", False)
    note = state.get("approval", {}).get("note", "")
    for action in incident.remediation_actions:
        action.approved = approved
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
    }
