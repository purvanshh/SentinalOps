from __future__ import annotations

from typing import Any


async def export_postmortem(
    *,
    incident_id: str,
    title: str,
    content: str,
) -> dict[str, Any]:
    return {
        "provider": "confluence",
        "incident_id": incident_id,
        "title": title,
        "exported": False,
        "content_length": len(content),
        "message": "Confluence export stub captured the postmortem payload.",
    }
