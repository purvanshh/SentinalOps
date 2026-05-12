from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, require_role
from api.middleware.auth import AuthenticatedUser
from api.schemas.incident import (
    AlertPayload,
    IncidentCreate,
    IncidentResponse,
    IncidentSummary,
    PostmortemResponse,
)
from agents.router_agent import classify_incident
from db.repositories.incident_repo import IncidentRepository
from db.repositories.postmortem_repo import PostmortemRepository
from memory.short_term.incident_state import IncidentStateStore
from workers.tasks.incident_pipeline import enqueue_incident_pipeline

router = APIRouter(prefix="/incidents", tags=["incidents"])


def _merge_runtime_state(incident, runtime_state: dict | None) -> dict:
    payload = IncidentResponse.model_validate(incident).model_dump(mode="json")
    if runtime_state:
        payload["operating_mode"] = runtime_state.get("operating_mode")
        payload["graph_status"] = runtime_state.get("graph_status")
        payload["fallback_activated"] = runtime_state.get("fallback_activated")
        payload["last_successful_step"] = runtime_state.get("last_successful_step")
        payload["provider_chain_result"] = runtime_state.get("provider_chain_result")
    return payload


@router.post("/webhook", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED)
async def create_incident_from_webhook(
    payload: AlertPayload,
    db: AsyncSession = Depends(get_db),
    _: AuthenticatedUser = Depends(require_role(["admin"])),
) -> IncidentResponse:
    repository = IncidentRepository(db)
    incident = await repository.create_from_alert(
        IncidentCreate(
            title=payload.title,
            severity=payload.severity,
            source=payload.source,
            summary=payload.summary,
            raw_payload=payload.model_dump(mode="json"),
        )
    )
    enqueue_incident_pipeline(str(incident.id))
    return IncidentResponse.model_validate(incident)


@router.get("", response_model=list[IncidentSummary])
async def list_incidents(
    db: AsyncSession = Depends(get_db),
    status_filter: str | None = None,
    _: AuthenticatedUser = Depends(require_role(["viewer"])),
) -> list[IncidentSummary]:
    repository = IncidentRepository(db)
    incidents = await repository.list(status_filter=status_filter)
    return [IncidentSummary.model_validate(incident) for incident in incidents]


@router.get("/{incident_id}", response_model=IncidentResponse)
async def get_incident(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: AuthenticatedUser = Depends(require_role(["viewer"])),
) -> IncidentResponse:
    repository = IncidentRepository(db)
    incident = await repository.get_with_agent_executions(incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    runtime_state = None
    if incident.graph_thread_id:
        from orchestration.graphs.main_graph import build_main_graph

        try:
            runtime_state = await build_main_graph().get_state(incident.graph_thread_id)
        except Exception:
            runtime_state = None
    if not runtime_state:
        runtime_state = await IncidentStateStore().load_state(str(incident_id))
    return IncidentResponse.model_validate(_merge_runtime_state(incident, runtime_state))


@router.post("/{incident_id}/classify", response_model=IncidentResponse)
async def classify_existing_incident(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: AuthenticatedUser = Depends(require_role(["operator"])),
) -> IncidentResponse:
    repository = IncidentRepository(db)
    incident = await repository.get(incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    await classify_incident(incident, db_session=db)
    refreshed = await repository.get_with_agent_executions(incident_id)
    if refreshed is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    return IncidentResponse.model_validate(refreshed)


@router.get("/{incident_id}/postmortems", response_model=list[PostmortemResponse])
async def list_postmortems(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: AuthenticatedUser = Depends(require_role(["viewer"])),
) -> list[PostmortemResponse]:
    repository = IncidentRepository(db)
    incident = await repository.get(incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    postmortem_repo = PostmortemRepository(db)
    rows = await postmortem_repo.list_postmortems(incident_id)
    return [PostmortemResponse.model_validate(row) for row in rows]
