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
    graph = build_main_graph()
    state = await graph.resume(
        incident.graph_thread_id,
        ResumeCommand(approved=payload.approved, note=payload.note, approved_by=user.user_id),
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
