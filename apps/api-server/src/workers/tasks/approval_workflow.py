from datetime import UTC, datetime, timedelta
from uuid import UUID

from core.config import get_settings
from db.repositories.incident_repo import IncidentRepository
from orchestration.interrupts.approval_store import ApprovalStore
from sqlalchemy.ext.asyncio import AsyncSession
from tools.slack.notifier import notify_approval_required


async def start_approval_workflow(
    incident_id: UUID,
    summary: str,
    actions: list[str],
    db_session: AsyncSession,
) -> None:
    repository = IncidentRepository(db_session)
    settings = get_settings()
    await repository.update_status(incident_id, "awaiting_approval")
    await ApprovalStore(db_session).create_approval_request(
        incident_id,
        summary=summary,
        actions=actions,
        expires_at=datetime.now(UTC) + timedelta(minutes=settings.approval_timeout_minutes),
    )
    await notify_approval_required(str(incident_id), summary)


async def process_approval_decision(
    incident_id: UUID,
    approved: bool,
    note: str,
    approved_by: str,
    db_session: AsyncSession,
) -> None:
    repository = IncidentRepository(db_session)
    incident = await repository.get_with_context(incident_id)
    if incident is None:
        return

    for action in incident.remediation_actions:
        action.approved = approved
        action.approved_by = approved_by
        action.status = "approved" if approved else "rejected"
        action.details = {**(action.details or {}), "approval_note": note}
        if approved:
            action.executed = True
            action.status = "executed"
    incident.status = "resolved" if approved else "approval_rejected"
    await db_session.commit()
