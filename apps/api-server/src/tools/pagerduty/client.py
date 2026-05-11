from __future__ import annotations

from typing import Any


async def sync_incident_status(
    incident_id: str,
    *,
    severity: str,
    status: str,
) -> dict[str, Any]:
    return {
        "provider": "pagerduty",
        "incident_id": incident_id,
        "severity": severity,
        "status": status,
        "synced": False,
        "message": "PagerDuty integration stub recorded the requested sync.",
    }
