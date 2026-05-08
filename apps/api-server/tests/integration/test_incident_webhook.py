from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from main import app


def test_incident_webhook_creates_incident(monkeypatch) -> None:
    client = TestClient(app)
    fake_incident = SimpleNamespace(
        id=uuid4(),
        title="API latency exceeded threshold",
        severity="high",
        status="open",
        source="prometheus",
        summary="Latency crossed p99 threshold for 5 minutes",
        raw_payload={"title": "API latency exceeded threshold"},
        agent_executions=[],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    async def fake_create_from_alert(self, data):
        return fake_incident

    monkeypatch.setattr(
        "db.repositories.incident_repo.IncidentRepository.create_from_alert",
        fake_create_from_alert,
    )
    monkeypatch.setattr(
        "api.routes.incidents.enqueue_incident_pipeline",
        lambda incident_id: incident_id,
    )

    response = client.post(
        "/incidents/webhook",
        json={
            "title": "API latency exceeded threshold",
            "summary": "Latency crossed p99 threshold for 5 minutes",
            "severity": "high",
            "source": "prometheus",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["title"] == "API latency exceeded threshold"
    assert payload["status"] == "open"
