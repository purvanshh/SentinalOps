from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
from main import app
from tests.auth_helpers import make_auth_header


def test_postmortem_listing_route_returns_items(monkeypatch) -> None:
    incident_id = uuid4()
    client = TestClient(app)

    async def fake_get(self, incident_id_arg):
        return SimpleNamespace(id=incident_id_arg)

    async def fake_list_postmortems(self, incident_id_arg):
        return [
            SimpleNamespace(
                id=uuid4(),
                incident_id=incident_id_arg,
                title="Postmortem: Test Incident",
                content="content",
                version=1,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        ]

    monkeypatch.setattr("db.repositories.incident_repo.IncidentRepository.get", fake_get)
    monkeypatch.setattr(
        "db.repositories.postmortem_repo.PostmortemRepository.list_postmortems",
        fake_list_postmortems,
    )

    response = client.get(
        f"/incidents/{incident_id}/postmortems", headers=make_auth_header("viewer")
    )

    assert response.status_code == 200
    assert response.json()[0]["title"] == "Postmortem: Test Incident"
