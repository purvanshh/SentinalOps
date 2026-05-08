from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from main import app
from memory.short_term.approval_state import clear_pending_approval, set_pending_approval
from tests.auth_helpers import make_auth_header


def test_approval_endpoint_processes_decision(monkeypatch) -> None:
    incident_id = uuid4()
    client = TestClient(app)
    set_pending_approval(
        incident_id,
        {
            "incident_id": incident_id,
            "status": "awaiting_approval",
            "summary": "Approval needed for rollback deployment",
            "actions": ["rollback deployment"],
            "created_at": datetime.now(UTC),
        },
    )

    async def fake_process(incident_id_arg, approved, note, db):
        return None

    async def fake_get(self, incident_id_arg):
        return SimpleNamespace(id=incident_id_arg, graph_thread_id=None)

    async def fake_get_with_context(self, incident_id_arg):
        return SimpleNamespace(
            id=incident_id_arg,
            status="resolved",
            remediation_actions=[],
            agent_executions=[],
            evidence_items=[],
            title="test",
            severity="high",
            source="prometheus",
            summary="summary",
            incident_type="deployment_regression",
            classification_confidence=0.9,
            classification_rationale="rationale",
            recommended_workflow="full_investigation",
            raw_payload={},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    monkeypatch.setattr("api.routes.approvals.process_approval_decision", fake_process)
    monkeypatch.setattr(
        "db.repositories.incident_repo.IncidentRepository.get",
        fake_get,
    )
    monkeypatch.setattr(
        "db.repositories.incident_repo.IncidentRepository.get_with_context",
        fake_get_with_context,
    )

    response = client.post(
        f"/approvals/{incident_id}",
        json={"approved": True, "note": "Proceed"},
        headers=make_auth_header("operator"),
    )

    clear_pending_approval(incident_id)
    assert response.status_code == 200
    assert response.json()["approved"] is True
