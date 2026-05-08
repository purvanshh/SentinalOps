from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from main import app


def test_graph_start_route_returns_thread_id(monkeypatch) -> None:
    incident_id = uuid4()
    client = TestClient(app)

    async def fake_get(self, incident_id_arg):
        return SimpleNamespace(id=incident_id_arg)

    class FakeGraph:
        async def ainvoke(self, initial_state):
            return {
                "thread_id": "thread-123",
                "status": "awaiting_approval",
                "incident_id": initial_state["incident_id"],
            }

    monkeypatch.setattr("db.repositories.incident_repo.IncidentRepository.get", fake_get)
    monkeypatch.setattr("api.routes.graph.build_main_graph", lambda: FakeGraph())

    response = client.post(f"/graph/incidents/{incident_id}/start")

    assert response.status_code == 200
    assert response.json()["thread_id"] == "thread-123"
