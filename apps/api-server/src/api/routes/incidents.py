from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
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
from workers.tasks.incident_pipeline import enqueue_incident_pipeline

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.post("/webhook", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED)
async def create_incident_from_webhook(
    payload: AlertPayload,
    db: AsyncSession = Depends(get_db),
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
async def list_incidents(db: AsyncSession = Depends(get_db), status_filter: str | None = None) -> list[IncidentSummary]:
    repository = IncidentRepository(db)
    incidents = await repository.list(status_filter=status_filter)
    return [IncidentSummary.model_validate(incident) for incident in incidents]


@router.get("/{incident_id}", response_model=IncidentResponse)
async def get_incident(incident_id: UUID, db: AsyncSession = Depends(get_db)) -> IncidentResponse:
    repository = IncidentRepository(db)
    incident = await repository.get_with_agent_executions(incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    return IncidentResponse.model_validate(incident)


@router.post("/{incident_id}/classify", response_model=IncidentResponse)
async def classify_existing_incident(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
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
async def list_postmortems(incident_id: UUID, db: AsyncSession = Depends(get_db)) -> list[PostmortemResponse]:
    repository = IncidentRepository(db)
    incident = await repository.get(incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    postmortem_repo = PostmortemRepository(db)
    rows = await postmortem_repo.list_postmortems(incident_id)
    return [PostmortemResponse.model_validate(row) for row in rows]
