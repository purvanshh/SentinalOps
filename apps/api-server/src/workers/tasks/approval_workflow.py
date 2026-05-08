from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from db.repositories.incident_repo import IncidentRepository
from memory.short_term.approval_state import set_pending_approval
from tools.slack.notifier import notify_approval_required


async def start_approval_workflow(
    incident_id: UUID,
    summary: str,
    actions: list[str],
    db_session: AsyncSession,
) -> None:
    repository = IncidentRepository(db_session)
    await repository.update_status(incident_id, "awaiting_approval")
    set_pending_approval(
        incident_id,
        {
            "incident_id": incident_id,
            "status": "awaiting_approval",
            "summary": summary,
            "actions": actions,
            "created_at": datetime.now(UTC),
        },
    )
    await notify_approval_required(str(incident_id), summary)


async def process_approval_decision(
    incident_id: UUID,
    approved: bool,
    note: str,
    db_session: AsyncSession,
) -> None:
    repository = IncidentRepository(db_session)
    incident = await repository.get_with_context(incident_id)
    if incident is None:
        return

    for action in incident.remediation_actions:
        action.approved = approved
        action.status = "approved" if approved else "rejected"
        action.details = {**(action.details or {}), "approval_note": note}
        if approved:
            action.executed = True
            action.status = "executed"
    incident.status = "resolved" if approved else "approval_rejected"
    await db_session.commit()
