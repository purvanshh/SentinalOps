from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from main import app
from memory.short_term.approval_state import clear_pending_approval, set_pending_approval
from tests.auth_helpers import make_auth_header


def test_protected_route_requires_token() -> None:
    client = TestClient(app)

    response = client.get("/incidents")

    assert response.status_code == 401


def test_viewer_cannot_approve(monkeypatch) -> None:
    incident_id = uuid4()
    client = TestClient(app)
    set_pending_approval(
        incident_id,
        {
            "incident_id": incident_id,
            "status": "awaiting_approval",
            "summary": "Approval needed",
            "actions": ["rollback deployment"],
            "created_at": datetime.now(UTC),
        },
    )

    async def fake_get(self, incident_id_arg):
        return SimpleNamespace(id=incident_id_arg, graph_thread_id=None)

    monkeypatch.setattr("db.repositories.incident_repo.IncidentRepository.get", fake_get)

    response = client.post(
        f"/approvals/{incident_id}",
        json={"approved": True, "note": "Proceed"},
        headers=make_auth_header("viewer"),
    )

    clear_pending_approval(incident_id)
    assert response.status_code == 403
