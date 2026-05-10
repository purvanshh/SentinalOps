from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, require_role
from api.middleware.auth import AuthenticatedUser
from api.schemas.approval import ApprovalDecisionRequest
from db.repositories.incident_repo import IncidentRepository
from orchestration.graphs.main_graph import build_main_graph
from orchestration.interrupts.commands import ResumeCommand
from orchestration.interrupts.approval_store import ApprovalStore
from tools.action_mapping import map_action_to_tool
from tools.execution_guard import create_approval_token

router = APIRouter(prefix="/graph", tags=["graph"])


@router.post("/incidents/{incident_id}/start")
async def start_graph(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: AuthenticatedUser = Depends(require_role(["operator"])),
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
    db: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(["operator"])),
) -> dict:
    repository = IncidentRepository(db)
    incident = await repository.get(incident_id)
    if incident is None or not incident.graph_thread_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Graph thread not found")
    approval_row = await ApprovalStore(db).get_approval(incident_id)
    if approval_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval request not found")
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
    db: AsyncSession = Depends(get_db),
    _: AuthenticatedUser = Depends(require_role(["viewer"])),
) -> dict:
    repository = IncidentRepository(db)
    incident = await repository.get(incident_id)
    if incident is None or not incident.graph_thread_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Graph thread not found")
    state = await build_main_graph().get_state(incident.graph_thread_id)
    return {"thread_id": incident.graph_thread_id, "state": state}


@router.get("/incidents/{incident_id}/graph-state")
async def graph_visual_state(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: AuthenticatedUser = Depends(require_role(["viewer"])),
) -> dict:
    repository = IncidentRepository(db)
    incident = await repository.get(incident_id)
    if incident is None or not incident.graph_thread_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Graph thread not found")
    state = await build_main_graph().get_state(incident.graph_thread_id)
    completed = set(state.get("completed_nodes", []))
    ordered_nodes = [
        "router",
        "dispatch_evidence",
        "metrics",
        "logs",
        "deployment",
        "root_cause",
        "risk",
        "remediation",
        "approval",
        "approval_interrupt",
        "execution",
        "postmortem",
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
    edges = [{"source": ordered_nodes[index], "target": ordered_nodes[index + 1]} for index in range(len(ordered_nodes) - 1)]
    return {"thread_id": incident.graph_thread_id, "nodes": nodes, "edges": edges, "state": state}
