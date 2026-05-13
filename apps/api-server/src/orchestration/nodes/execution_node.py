from __future__ import annotations

import uuid
from datetime import datetime, timezone

from agents.risk_agent.action_mapper import map_action_to_category
from core.resilience.operating_mode import OperatingMode
from db.repositories.incident_repo import IncidentRepository
from db.repositories.risk_repo import RiskRepository
from db.session import SessionLocal
from observability.logging import bind_execution_id
from observability.metrics import observe_remediation_action
from tools.action_mapping import map_action_to_tool
from tools.base import ToolCall
from tools.execution_guard import ExecutionGuardError
from tools.risk_classifier import classify_action_risk_tier
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

    execution_id = str(uuid.uuid4())
    bind_execution_id(execution_id)

    registry = build_runtime_registry()
    risk_repository = RiskRepository(session)
    executed_actions: list[str] = []
    verification_results: list[dict] = []
    operating_mode = str(state.get("operating_mode", OperatingMode.FULL.value))

    if operating_mode in {OperatingMode.SAFE_MODE.value, OperatingMode.OBSERVE_ONLY.value}:
        incident.status = "observe_only"
        await session.commit()
        return {
            "execution": {
                "approved": False,
                "executed_actions": [],
                "verification_results": [],
                "execution_disabled": True,
                "reason": f"Automated execution disabled in {operating_mode}",
            },
            "status": incident.status,
            "approved_actions": [],
            "completed_nodes": ["execution_actions"],
            "last_successful_step": "execution_actions",
            "graph_status": "observe_only",
        }

    if not incident.remediation_actions:
        incident.status = "resolved"
        await session.commit()
        return {
            "execution": {
                "approved": False,
                "executed_actions": [],
                "verification_results": [],
                "noop": True,
                "reason": "No remediation actions were generated",
            },
            "status": incident.status,
            "approved_actions": [],
            "completed_nodes": ["execution_actions"],
            "last_successful_step": "execution_actions",
        }

    for action in incident.remediation_actions:
        action.approved = approved
        action.approved_by = approved_by
        action.details = {**(action.details or {}), "approval_note": note}
        if not approved:
            action.status = "rejected"
            continue

        tool_name, arguments = map_action_to_tool(action.action)
        risk_tier = classify_action_risk_tier(action.action)
        rollback_path = f"rollback_{tool_name}" if "rollback" not in tool_name else None
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
                observe_remediation_action("failed")
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
                "execution_id": execution_id,
                "executed_at": datetime.now(timezone.utc).isoformat(),
                "tool_name": tool_name,
                "risk_tier": risk_tier.value,
                "rollback_path": rollback_path,
                "approved_by": approved_by,
                "tool_result": result.output,
                "verification": verify_result.output,
            }
            executed_actions.append(action.action)
            verification_results.append(verify_result.model_dump(mode="json"))
            observe_remediation_action("executed")
            await risk_repository.record_remediation_outcome(
                action_name=action.action,
                category=map_action_to_category(action.action),
                success=bool((verify_result.output or {}).get("within_range", False)),
                execution_time_seconds=60.0,
                severity_on_failure=0.3,
            )
        except ExecutionGuardError as exc:
            action.status = "blocked"
            action.details = {
                **action.details,
                "execution_id": execution_id,
                "risk_tier": risk_tier.value,
                "guard_error": str(exc),
            }
            observe_remediation_action("blocked")

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
        "completed_nodes": ["execution_actions"],
        "last_successful_step": "execution_actions",
    }
