from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.schemas.approval import ApprovalDecisionRequest
from db.repositories.incident_repo import IncidentRepository
from memory.short_term.approval_state import clear_pending_approval
from orchestration.graphs.main_graph import build_main_graph
from orchestration.interrupts.commands import ResumeCommand

router = APIRouter(prefix="/graph", tags=["graph"])


@router.post("/incidents/{incident_id}/start")
async def start_graph(incident_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    repository = IncidentRepository(db)
    incident = await repository.get(incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    graph = build_main_graph()
    state = await graph.ainvoke({"incident_id": str(incident_id)})
    return {"thread_id": state["thread_id"], "status": state.get("status"), "state": state}


@router.post("/incidents/{incident_id}/resume")
async def resume_graph(
    incident_id: UUID,
    payload: ApprovalDecisionRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    repository = IncidentRepository(db)
    incident = await repository.get(incident_id)
    if incident is None or not incident.graph_thread_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Graph thread not found")
    graph = build_main_graph()
    state = await graph.resume(
        incident.graph_thread_id,
        ResumeCommand(approved=payload.approved, note=payload.note),
    )
    clear_pending_approval(incident_id)
    return {"thread_id": incident.graph_thread_id, "status": state.get("status"), "state": state}
