from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.schemas.approval import ApprovalDecisionRequest, ApprovalQueueItem, ApprovalResponse
from db.repositories.incident_repo import IncidentRepository
from memory.short_term.approval_state import (
    clear_pending_approval,
    get_pending_approval,
    list_pending_approvals,
)
from workers.tasks.approval_workflow import process_approval_decision

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("", response_model=list[ApprovalQueueItem])
async def pending_approvals() -> list[ApprovalQueueItem]:
    return [ApprovalQueueItem.model_validate(item) for item in list_pending_approvals()]


@router.post("/{incident_id}", response_model=ApprovalResponse)
async def decide_approval(
    incident_id: UUID,
    payload: ApprovalDecisionRequest,
    db: AsyncSession = Depends(get_db),
) -> ApprovalResponse:
    pending = get_pending_approval(incident_id)
    if pending is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found")

    await process_approval_decision(incident_id, payload.approved, payload.note, db)
    clear_pending_approval(incident_id)

    repository = IncidentRepository(db)
    incident = await repository.get_with_context(incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    return ApprovalResponse.model_validate(
        {
            "incident_id": incident.id,
            "approved": payload.approved,
            "status": incident.status,
            "note": payload.note,
        }
    )
