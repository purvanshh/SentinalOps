from datetime import UTC, datetime, timedelta

from core.config import get_settings
from memory.short_term.approval_state import list_pending_approvals
from tools.slack.notifier import notify_approval_escalation


async def check_pending_approvals() -> list[str]:
    settings = get_settings()
    escalations: list[str] = []
    now = datetime.now(UTC)
    for item in list_pending_approvals():
        created_at = item["created_at"]
        if isinstance(created_at, str):
            created_at_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        else:
            created_at_dt = created_at
        age = now - created_at_dt
        if age >= timedelta(minutes=settings.approval_auto_reject_minutes):
            escalations.append(f"{item['incident_id']}:auto_reject")
            await notify_approval_escalation(str(item["incident_id"]), "approval auto-rejected after timeout")
        elif age >= timedelta(minutes=settings.approval_timeout_minutes):
            escalations.append(f"{item['incident_id']}:escalated")
            await notify_approval_escalation(str(item["incident_id"]), "approval timeout reached")
    return escalations
