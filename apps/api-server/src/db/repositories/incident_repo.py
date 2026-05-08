from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import selectinload

from api.schemas.incident import IncidentCreate
from db.models import AgentExecution, Incident
from db.repositories import BaseRepository


class IncidentRepository(BaseRepository):
    async def create_from_alert(self, data: IncidentCreate) -> Incident:
        incident = Incident(
            title=data.title,
            severity=data.severity,
            status=data.status,
            source=data.source,
            summary=data.summary,
            raw_payload=data.raw_payload,
        )
        self.session.add(incident)
        await self.session.commit()
        await self.session.refresh(incident)
        return incident

    async def list(self, status_filter: str | None = None) -> list[Incident]:
        query: Select[tuple[Incident]] = select(Incident).order_by(Incident.created_at.desc())
        if status_filter:
            query = query.where(Incident.status == status_filter)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_with_agent_executions(self, incident_id: UUID) -> Incident | None:
        query = (
            select(Incident)
            .where(Incident.id == incident_id)
            .options(selectinload(Incident.agent_executions))
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def update_status(self, incident_id: UUID, status: str) -> Incident | None:
        incident = await self.get_with_agent_executions(incident_id)
        if incident is None:
            return None
        incident.status = status
        await self.session.commit()
        await self.session.refresh(incident)
        return incident

    async def create_agent_execution(
        self,
        incident_id: UUID,
        agent_name: str,
        input_payload: dict | None,
        output_payload: dict | None,
        status: str,
        latency: float | None = None,
    ) -> AgentExecution:
        execution = AgentExecution(
            incident_id=incident_id,
            agent_name=agent_name,
            input=input_payload,
            output=output_payload,
            status=status,
            latency=latency,
        )
        self.session.add(execution)
        await self.session.commit()
        await self.session.refresh(execution)
        return execution
