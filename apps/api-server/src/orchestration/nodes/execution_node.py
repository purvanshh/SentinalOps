from __future__ import annotations

from db.repositories.incident_repo import IncidentRepository
from db.repositories.risk_repo import RiskRepository
from db.session import SessionLocal
from agents.risk_agent.action_mapper import map_action_to_category
from tools.action_mapping import map_action_to_tool
from tools.base import ToolCall
from tools.execution_guard import ExecutionGuardError
from tools.runtime_tools import build_runtime_registry


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
    approval_token = state.get("approval", {}).get("approval_token")

    registry = build_runtime_registry()
    risk_repository = RiskRepository(session)
    executed_actions: list[str] = []
    verification_results: list[dict] = []

    for action in incident.remediation_actions:
        action.approved = approved
        action.approved_by = approved_by
        action.details = {**(action.details or {}), "approval_note": note}
        if not approved:
            action.status = "rejected"
            continue

        tool_name, arguments = map_action_to_tool(action.action)
        try:
            result = await registry.execute(
                ToolCall(name=tool_name, arguments=arguments),
                execution_context={
                    "incident_id": str(incident.id),
                    "actor_id": approved_by,
                    "approval_token": approval_token,
                },
                session=session,
            )
            if not result.success:
                action.status = "failed"
                continue

            verify_result = await registry.execute(
                ToolCall(
                    name="verify_metric",
                    arguments={
                        "metric_name": action.details.get("verification_metric", "latency_p99"),
                        "expected_min": 0,
                        "expected_max": 1000,
                    },
                ),
                execution_context={
                    "incident_id": str(incident.id),
                    "actor_id": approved_by,
                },
                session=session,
            )
            action.executed = True
            action.status = "executed"
            action.details = {
                **action.details,
                "tool_name": tool_name,
                "tool_result": result.output,
                "verification": verify_result.output,
            }
            executed_actions.append(action.action)
            verification_results.append(verify_result.model_dump(mode="json"))
            await risk_repository.record_remediation_outcome(
                action_name=action.action,
                category=map_action_to_category(action.action),
                success=bool((verify_result.output or {}).get("within_range", False)),
                execution_time_seconds=60.0,
                severity_on_failure=0.3,
            )
        except ExecutionGuardError as exc:
            action.status = "blocked"
            action.details = {**action.details, "guard_error": str(exc)}

    incident.status = "resolved" if approved else "approval_rejected"
    await session.commit()
    return {
        "execution": {
            "approved": approved,
            "executed_actions": executed_actions,
            "verification_results": verification_results,
        },
        "status": incident.status,
        "approved_actions": executed_actions,
        "completed_nodes": ["execution"],
    }
