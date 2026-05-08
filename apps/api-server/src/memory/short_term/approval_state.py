from datetime import UTC, datetime
from typing import Any
from uuid import UUID


_PENDING_APPROVALS: dict[str, dict[str, Any]] = {}


def set_pending_approval(incident_id: UUID, payload: dict[str, Any]) -> None:
    _PENDING_APPROVALS[str(incident_id)] = {
        **payload,
        "updated_at": datetime.now(UTC).isoformat(),
    }


def get_pending_approval(incident_id: UUID | str) -> dict[str, Any] | None:
    return _PENDING_APPROVALS.get(str(incident_id))


def clear_pending_approval(incident_id: UUID | str) -> None:
    _PENDING_APPROVALS.pop(str(incident_id), None)


def list_pending_approvals() -> list[dict[str, Any]]:
    return list(_PENDING_APPROVALS.values())
