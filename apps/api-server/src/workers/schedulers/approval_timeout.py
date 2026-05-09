from datetime import UTC, datetime, timedelta

from core.config import get_settings
from db.session import SessionLocal
from orchestration.interrupts.approval_store import ApprovalStore
from workers.queues import celery_app
from workers.tasks.approval_escalation import escalate_approval


async def check_pending_approvals() -> list[str]:
    settings = get_settings()
    escalations: list[str] = []
    now = datetime.now(UTC)
    async with SessionLocal() as session:
        rows = await ApprovalStore(session).list_pending_approvals()
    for item in rows:
        expires_at = datetime.fromisoformat(item.expires_at)
        age = now - item.created_at
        if now >= expires_at + timedelta(minutes=settings.approval_auto_reject_minutes - settings.approval_timeout_minutes):
            escalations.append(f"{item.incident_id}:auto_reject")
            escalate_approval.delay(str(item.incident_id))
        elif age >= timedelta(minutes=settings.approval_timeout_minutes):
            escalations.append(f"{item.incident_id}:escalated")
            escalate_approval.delay(str(item.incident_id))
    return escalations


@celery_app.task(name="workers.schedulers.scan_pending_approvals")
def scan_pending_approvals() -> list[str]:
    import asyncio

    return asyncio.run(check_pending_approvals())
