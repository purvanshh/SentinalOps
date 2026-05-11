from db.repositories.incident_repo import IncidentRepository
from db.session import SessionLocal
from workers.tasks.approval_workflow import start_approval_workflow


async def approval_node(state: dict, session=None) -> dict:
    if session is None:
        async with SessionLocal() as owned_session:
            return await approval_node(state, owned_session)
    remediation = state.get("remediation_plan", {})
    steps = remediation.get("steps", [])
    risky_actions = [step["action"] for step in steps if step.get("requires_approval")]
    if not risky_actions:
        return {
            "approval": {"required": False},
            "status": "ready_for_execution",
            "completed_nodes": ["approval_gate"],
        }

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
        "approval_request": {
            "required": True,
            "actions": risky_actions,
            "status": "awaiting_approval",
            "summary": remediation.get("summary", "Approval required for remediation"),
        },
        "status": "awaiting_approval",
        "completed_nodes": ["approval_gate"],
    }
