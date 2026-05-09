from datetime import UTC, datetime, timedelta

from core.config import get_settings
from db.session import SessionLocal
from orchestration.interrupts.approval_store import ApprovalStore
from tools.slack.notifier import notify_approval_escalation


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
            await notify_approval_escalation(str(item.incident_id), "approval auto-rejected after timeout")
        elif age >= timedelta(minutes=settings.approval_timeout_minutes):
            escalations.append(f"{item.incident_id}:escalated")
            await notify_approval_escalation(str(item.incident_id), "approval timeout reached")
    return escalations
