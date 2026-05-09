from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import selectinload

from api.schemas.incident import IncidentCreate
from db.models import AgentExecution, EvidenceItem, Incident, RemediationAction
from db.repositories import BaseRepository
from observability.metrics import observe_agent_execution, observe_incident_created


class IncidentRepository(BaseRepository):
    def _coerce_uuid(self, value: UUID | str) -> UUID:
        return value if isinstance(value, UUID) else UUID(str(value))

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
        observe_incident_created(incident.source)
        return incident

    async def list(self, status_filter: str | None = None) -> list[Incident]:
        query: Select[tuple[Incident]] = select(Incident).order_by(Incident.created_at.desc())
        if status_filter:
            query = query.where(Incident.status == status_filter)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_with_agent_executions(self, incident_id: UUID | str) -> Incident | None:
        incident_uuid = self._coerce_uuid(incident_id)
        query = (
            select(Incident)
            .where(Incident.id == incident_uuid)
            .options(selectinload(Incident.agent_executions))
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_with_context(self, incident_id: UUID | str) -> Incident | None:
        incident_uuid = self._coerce_uuid(incident_id)
        query = (
            select(Incident)
            .where(Incident.id == incident_uuid)
            .options(
                selectinload(Incident.agent_executions),
                selectinload(Incident.evidence_items),
                selectinload(Incident.remediation_actions),
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def update_status(self, incident_id: UUID | str, status: str) -> Incident | None:
        incident = await self.get_with_agent_executions(incident_id)
        if incident is None:
            return None
        incident.status = status
        await self.session.commit()
        await self.session.refresh(incident)
        return incident

    async def update_root_cause(
        self,
        incident_id: UUID | str,
        *,
        root_cause_status: str,
        root_cause_confidence: float | None,
    ) -> Incident | None:
        incident = await self.get(incident_id)
        if incident is None:
            return None
        incident.root_cause_status = root_cause_status
        incident.root_cause_confidence = root_cause_confidence
        await self.session.commit()
        await self.session.refresh(incident)
        return incident

    async def update_graph_thread_id(self, incident_id: UUID | str, thread_id: str) -> Incident | None:
        incident = await self.get(incident_id)
        if incident is None:
            return None
        incident.graph_thread_id = thread_id
        await self.session.commit()
        await self.session.refresh(incident)
        return incident

    async def update_incident_metrics(
        self,
        incident_id: UUID | str,
        *,
        first_anomaly_at: str | None,
        mitigated_at: str | None,
        resolved_at: str | None,
        ttd_seconds: float | None,
        ttm_seconds: float | None,
        ttr_seconds: float | None,
    ) -> Incident | None:
        incident = await self.get(incident_id)
        if incident is None:
            return None
        incident.first_anomaly_at = first_anomaly_at
        incident.mitigated_at = mitigated_at
        incident.resolved_at = resolved_at
        incident.ttd_seconds = ttd_seconds
        incident.ttm_seconds = ttm_seconds
        incident.ttr_seconds = ttr_seconds
        await self.session.commit()
        await self.session.refresh(incident)
        return incident

    async def get(self, incident_id: UUID | str) -> Incident | None:
        incident_uuid = self._coerce_uuid(incident_id)
        query = select(Incident).where(Incident.id == incident_uuid)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def update_classification(
        self,
        incident_id: UUID | str,
        *,
        incident_type: str,
        severity: str,
        confidence: float,
        rationale: str,
        recommended_workflow: str,
        status: str,
    ) -> Incident | None:
        incident = await self.get(incident_id)
        if incident is None:
            return None
        incident.incident_type = incident_type
        incident.severity = severity
        incident.classification_confidence = confidence
        incident.classification_rationale = rationale
        incident.recommended_workflow = recommended_workflow
        incident.status = status
        await self.session.commit()
        await self.session.refresh(incident)
        return incident

    async def create_agent_execution(
        self,
        incident_id: UUID | str,
        agent_name: str,
        input_payload: dict | None,
        output_payload: dict | None,
        status: str,
        latency: float | None = None,
    ) -> AgentExecution:
        incident_uuid = self._coerce_uuid(incident_id)
        execution = AgentExecution(
            incident_id=incident_uuid,
            agent_name=agent_name,
            input=input_payload,
            output=output_payload,
            status=status,
            latency=latency,
        )
        self.session.add(execution)
        await self.session.commit()
        await self.session.refresh(execution)
        observe_agent_execution(agent_name, status, latency)
        return execution

    async def replace_evidence_items(
        self,
        incident_id: UUID | str,
        evidence_items: list[dict],
    ) -> list[EvidenceItem]:
        incident = await self.get_with_context(incident_id)
        if incident is None:
            return []
        incident_uuid = self._coerce_uuid(incident_id)

        for item in list(incident.evidence_items):
            await self.session.delete(item)
        await self.session.flush()

        created_items: list[EvidenceItem] = []
        for payload in evidence_items:
            item = EvidenceItem(
                incident_id=incident_uuid,
                source=payload["source"],
                item_type=payload["item_type"],
                item_key=payload["item_key"],
                content=payload["content"],
            )
            self.session.add(item)
            created_items.append(item)

        await self.session.commit()
        for item in created_items:
            await self.session.refresh(item)
        return created_items

    async def list_agent_executions(self, incident_id: UUID | str) -> list[AgentExecution]:
        incident_uuid = self._coerce_uuid(incident_id)
        query = (
            select(AgentExecution)
            .where(AgentExecution.incident_id == incident_uuid)
            .order_by(AgentExecution.created_at.asc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def replace_remediation_actions(
        self,
        incident_id: UUID | str,
        steps: list[dict],
    ) -> list[RemediationAction]:
        incident = await self.get_with_context(incident_id)
        if incident is None:
            return []
        incident_uuid = self._coerce_uuid(incident_id)
        for action in list(incident.remediation_actions):
            await self.session.delete(action)
        await self.session.flush()

        rows: list[RemediationAction] = []
        for step in steps:
            action = RemediationAction(
                incident_id=incident_uuid,
                action=step["action"],
                details={
                    "rationale": step["rationale"],
                    "verification_metric": step["verification_metric"],
                    "priority": step["priority"],
                },
                requires_approval=step["requires_approval"],
                approved=False,
                executed=False,
                status="pending",
            )
            self.session.add(action)
            rows.append(action)
        await self.session.commit()
        for row in rows:
            await self.session.refresh(row)
        return rows
