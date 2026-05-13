from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
from main import app
from tests.auth_helpers import make_auth_header


def test_protected_route_requires_token() -> None:
    client = TestClient(app)

    response = client.get("/incidents")

    assert response.status_code == 401


def test_viewer_cannot_approve(monkeypatch) -> None:
    incident_id = uuid4()
    client = TestClient(app)

    async def fake_pending(self, incident_id_arg):
        return SimpleNamespace(incident_id=incident_id_arg, status="pending")

    async def fake_get(self, incident_id_arg):
        return SimpleNamespace(id=incident_id_arg, graph_thread_id=None)

    monkeypatch.setattr(
        "orchestration.interrupts.approval_store.ApprovalStore.get_pending_approval",
        fake_pending,
    )
    monkeypatch.setattr("db.repositories.incident_repo.IncidentRepository.get", fake_get)

    response = client.post(
        f"/approvals/{incident_id}",
        json={"approved": True, "note": "Proceed"},
        headers=make_auth_header("viewer"),
    )

    assert response.status_code == 403
