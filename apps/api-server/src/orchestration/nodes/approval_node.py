from db.repositories.incident_repo import IncidentRepository
from workers.tasks.approval_workflow import start_approval_workflow


async def approval_node(state: dict, session) -> dict:
    remediation = state.get("remediation", {})
    steps = remediation.get("steps", [])
    risky_actions = [step["action"] for step in steps if step.get("requires_approval")]
    if not risky_actions:
        return {"approval": {"required": False}, "status": "ready_for_execution"}

    repository = IncidentRepository(session)
    incident = await repository.get(state["incident_id"])
    if incident is None:
        return {}
    await start_approval_workflow(
        incident.id,
        remediation.get("summary", "Approval required for remediation"),
        risky_actions,
        session,
    )
    return {
        "approval": {
            "required": True,
            "actions": risky_actions,
            "status": "awaiting_approval",
        },
        "status": "awaiting_approval",
    }
