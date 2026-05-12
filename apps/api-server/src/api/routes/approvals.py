from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, require_role
from api.middleware.auth import AuthenticatedUser
from api.schemas.approval import ApprovalDecisionRequest, ApprovalQueueItem, ApprovalResponse
from db.repositories.incident_repo import IncidentRepository
from orchestration.graphs.main_graph import build_main_graph
from orchestration.interrupts.commands import ResumeCommand
from orchestration.interrupts.approval_store import ApprovalStore
from tools.action_mapping import map_action_to_tool
from tools.execution_guard import create_approval_token
from workers.tasks.approval_workflow import process_approval_decision

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("", response_model=list[ApprovalQueueItem])
async def pending_approvals(
    db: AsyncSession = Depends(get_db),
    _: AuthenticatedUser = Depends(require_role(["viewer"])),
) -> list[ApprovalQueueItem]:
    rows = await ApprovalStore(db).list_pending_approvals()
    return [
        ApprovalQueueItem.model_validate(
            {
                "incident_id": row.incident_id,
                "status": row.status,
                "summary": row.summary,
                "actions": row.actions,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
                "expires_at": row.expires_at,
            }
        )
        for row in rows
    ]


@router.post("/{incident_id}", response_model=ApprovalResponse)
async def decide_approval(
    incident_id: UUID,
    payload: ApprovalDecisionRequest,
    db: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(["operator"])),
) -> ApprovalResponse:
    approval_store = ApprovalStore(db)
    pending = await approval_store.get_pending_approval(incident_id)
    if pending is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found")

    repository = IncidentRepository(db)
    incident = await repository.get(incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    if incident.graph_thread_id:
        approval_token = None
        if payload.approved:
            approved_tools = [map_action_to_tool(action)[0] for action in pending.actions]
            approval_token = create_approval_token(
                incident_id=str(incident_id),
                action_ids=approved_tools,
                approved_by=user.user_id,
                expires_at=datetime.fromisoformat(pending.expires_at),
            )
        await approval_store.record_approval(
            incident_id,
            approved=payload.approved,
            approved_by=user.user_id,
            note=payload.note,
        )
        graph = build_main_graph()
        await graph.resume(
            incident.graph_thread_id,
            ResumeCommand(
                approved=payload.approved,
                note=payload.note,
                approved_by=user.user_id,
                approval_token=approval_token,
            ),
        )
    else:
        await process_approval_decision(incident_id, payload.approved, payload.note, user.user_id, db)
        approval_token = None
        await approval_store.record_approval(
            incident_id,
            approved=payload.approved,
            approved_by=user.user_id,
            note=payload.note,
        )

    incident = await repository.get_with_context(incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    return ApprovalResponse.model_validate(
        {
            "incident_id": incident.id,
            "approved": payload.approved,
            "status": incident.status,
            "note": payload.note,
            "approval_token": approval_token,
        }
    )
