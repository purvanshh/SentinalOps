from datetime import UTC, datetime, timedelta
from uuid import UUID

from db.session import SessionLocal
from db.repositories.incident_repo import IncidentRepository
from orchestration.interrupts.approval_store import ApprovalStore
from tools.slack.notifier import notify_approval_escalation
from workers.async_utils import run_async
from workers.queues import celery_app
from core.config import get_settings


@celery_app.task(name="workers.tasks.escalate_approval", reject_on_worker_lost=True, acks_late=True)
def escalate_approval(incident_id: str) -> None:
    run_async(_escalate_approval(UUID(incident_id)))


async def _escalate_approval(incident_id: UUID) -> None:
    settings = get_settings()
    async with SessionLocal() as session:
        store = ApprovalStore(session)
        approval = await store.get_pending_approval(incident_id)
        if approval is None:
            return

        expires_at = datetime.fromisoformat(approval.expires_at)
        now = datetime.now(UTC)
        incident_repo = IncidentRepository(session)
        incident = await incident_repo.get_with_context(incident_id)
        if incident is None:
            return

        if now >= expires_at + timedelta(minutes=settings.approval_auto_reject_minutes - settings.approval_timeout_minutes):
            await store.record_approval(
                incident_id,
                approved=False,
                approved_by="system:auto-reject",
                note="Auto-rejected after approval timeout",
            )
            incident.status = "approval_rejected"
            await session.commit()
            await notify_approval_escalation(str(incident_id), "Auto-rejected after 30 minute timeout")
            return

        await notify_approval_escalation(
            str(incident_id),
            f"Escalated to backup on-call: {', '.join(settings.backup_oncall_list)}",
        )
