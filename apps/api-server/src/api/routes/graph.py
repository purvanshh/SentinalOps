from datetime import datetime
from uuid import UUID

from api.dependencies import get_db, require_role
from api.middleware.auth import AuthenticatedUser
from api.schemas.approval import ApprovalDecisionRequest
from db.repositories.incident_repo import IncidentRepository
from db.repositories.task_repo import PendingTaskRepository
from fastapi import APIRouter, Depends, HTTPException, status
from memory.short_term.incident_state import IncidentStateStore
from orchestration.checkpointing.checkpoint import WorkflowCheckpointStore
from orchestration.graphs.main_graph import build_main_graph
from orchestration.interrupts.approval_store import ApprovalStore
from orchestration.interrupts.commands import ResumeCommand
from sqlalchemy.ext.asyncio import AsyncSession
from tools.action_mapping import map_action_to_tool
from tools.execution_guard import create_approval_token

router = APIRouter(prefix="/graph", tags=["graph"])
DB_DEPENDENCY = Depends(get_db)
VIEWER_ROLE_DEPENDENCY = Depends(require_role(["viewer"]))
OPERATOR_ROLE_DEPENDENCY = Depends(require_role(["operator"]))


@router.post("/incidents/{incident_id}/start")
async def start_graph(
    incident_id: UUID,
    db: AsyncSession = DB_DEPENDENCY,
    _: AuthenticatedUser = OPERATOR_ROLE_DEPENDENCY,
) -> dict:
    repository = IncidentRepository(db)
    incident = await repository.get(incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    graph = build_main_graph()
    state = await graph.ainvoke({"incident_id": str(incident_id)})
    await repository.update_graph_thread_id(incident_id, state["thread_id"])
    return {"thread_id": state["thread_id"], "status": state.get("status"), "state": state}


@router.post("/incidents/{incident_id}/resume")
async def resume_graph(
    incident_id: UUID,
    payload: ApprovalDecisionRequest,
    db: AsyncSession = DB_DEPENDENCY,
    user: AuthenticatedUser = OPERATOR_ROLE_DEPENDENCY,
) -> dict:
    repository = IncidentRepository(db)
    incident = await repository.get(incident_id)
    if incident is None or not incident.graph_thread_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Graph thread not found")
    approval_row = await ApprovalStore(db).get_approval(incident_id)
    if approval_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Approval request not found"
        )
    approval_token = ""
    if payload.approved:
        approval_token = create_approval_token(
            incident_id=str(incident_id),
            action_ids=[map_action_to_tool(action)[0] for action in approval_row.actions],
            approved_by=user.user_id,
            expires_at=datetime.fromisoformat(approval_row.expires_at),
        )
    graph = build_main_graph()
    state = await graph.resume(
        incident.graph_thread_id,
        ResumeCommand(
            approved=payload.approved,
            note=payload.note,
            approved_by=user.user_id,
            approval_token=approval_token,
        ),
    )
    await ApprovalStore(db).record_approval(
        incident_id,
        approved=payload.approved,
        approved_by=user.user_id,
        note=payload.note,
    )
    return {"thread_id": incident.graph_thread_id, "status": state.get("status"), "state": state}


@router.get("/incidents/{incident_id}/state")
async def graph_state(
    incident_id: UUID,
    db: AsyncSession = DB_DEPENDENCY,
    _: AuthenticatedUser = VIEWER_ROLE_DEPENDENCY,
) -> dict:
    repository = IncidentRepository(db)
    incident = await repository.get(incident_id)
    if incident is None or not incident.graph_thread_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Graph thread not found")
    state = await build_main_graph().get_state(incident.graph_thread_id)
    if not state:
        state = await IncidentStateStore().load_state(str(incident_id)) or {}
    return {"thread_id": incident.graph_thread_id, "state": state}


@router.get("/incidents/{incident_id}/graph-state")
async def graph_visual_state(
    incident_id: UUID,
    db: AsyncSession = DB_DEPENDENCY,
    _: AuthenticatedUser = VIEWER_ROLE_DEPENDENCY,
) -> dict:
    repository = IncidentRepository(db)
    incident = await repository.get(incident_id)
    if incident is None or not incident.graph_thread_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Graph thread not found")
    state = await build_main_graph().get_state(incident.graph_thread_id)
    if not state:
        state = await IncidentStateStore().load_state(str(incident_id)) or {}
    completed = set(state.get("completed_nodes", []))
    ordered_nodes = [
        "router",
        "dispatch_evidence",
        "metrics",
        "logs",
        "deployment",
        "root_cause_analysis",
        "risk",
        "remediation",
        "approval_gate",
        "approval_interrupt",
        "execution_actions",
        "postmortem_report",
    ]
    nodes = [
        {
            "id": node_name,
            "status": (
                "completed"
                if node_name in completed
                else "active"
                if node_name == state.get("current_node")
                else "pending"
            ),
        }
        for node_name in ordered_nodes
    ]
    edges = [
        {"source": ordered_nodes[index], "target": ordered_nodes[index + 1]}
        for index in range(len(ordered_nodes) - 1)
    ]
    return {"thread_id": incident.graph_thread_id, "nodes": nodes, "edges": edges, "state": state}


@router.get("/incidents/{incident_id}/trace")
async def graph_trace(
    incident_id: UUID,
    db: AsyncSession = DB_DEPENDENCY,
    _: AuthenticatedUser = VIEWER_ROLE_DEPENDENCY,
) -> dict:
    repository = IncidentRepository(db)
    incident = await repository.get_with_context(incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    graph_state_payload = {}
    if incident.graph_thread_id:
        graph_state_payload = await build_main_graph().get_state(incident.graph_thread_id)
    if not graph_state_payload:
        graph_state_payload = await IncidentStateStore().load_state(str(incident_id)) or {}
    pending_task = await PendingTaskRepository(db).get_task(
        incident_id,
        "workers.tasks.run_incident_pipeline",
    )
    latest_checkpoint = None
    if incident.graph_thread_id:
        latest_checkpoint = await WorkflowCheckpointStore().latest(incident.graph_thread_id)
    return {
        "incident_id": str(incident_id),
        "thread_id": incident.graph_thread_id,
        "status": incident.status,
        "operating_mode": graph_state_payload.get("operating_mode"),
        "graph_status": graph_state_payload.get("graph_status"),
        "fallback_activated": graph_state_payload.get("fallback_activated"),
        "last_successful_step": graph_state_payload.get("last_successful_step"),
        "agent_executions": [
            {
                "id": str(execution.id),
                "agent_name": execution.agent_name,
                "status": execution.status,
                "latency": execution.latency,
                "created_at": execution.created_at.isoformat(),
                "input": execution.input,
                "output": execution.output,
            }
            for execution in incident.agent_executions
        ],
        "remediation_actions": [
            {
                "id": str(action.id),
                "action": action.action,
                "status": action.status,
                "approved": action.approved,
                "executed": action.executed,
                "requires_approval": action.requires_approval,
                "details": action.details,
            }
            for action in incident.remediation_actions
        ],
        "task_recovery": (
            {
                "status": pending_task.status,
                "attempts": pending_task.attempts,
                "last_error": pending_task.last_error,
                "recovery": pending_task.payload.get("recovery", {}),
            }
            if pending_task is not None
            else None
        ),
        "latest_checkpoint": (
            {
                "node_name": latest_checkpoint.node_name,
                "status": latest_checkpoint.status,
                "created_at": latest_checkpoint.created_at.isoformat(),
                "state_hash": latest_checkpoint.state_hash,
            }
            if latest_checkpoint is not None
            else None
        ),
        "graph_state": graph_state_payload,
    }
