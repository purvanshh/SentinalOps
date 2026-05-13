from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
from main import app
from tests.auth_helpers import make_auth_header


def test_approval_endpoint_processes_decision(monkeypatch) -> None:
    incident_id = uuid4()
    client = TestClient(app)

    async def fake_process(incident_id_arg, approved, note, approved_by, db):
        return None

    async def fake_get_pending(self, incident_id_arg):
        return SimpleNamespace(
            incident_id=incident_id_arg,
            status="pending",
            summary="Approval needed for rollback deployment",
            actions=["rollback deployment"],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            expires_at=datetime.now(UTC).isoformat(),
        )

    async def fake_record(self, incident_id_arg, *, approved, approved_by, note):
        return SimpleNamespace(
            incident_id=incident_id_arg, approved=approved, approved_by=approved_by, note=note
        )

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
        "orchestration.interrupts.approval_store.ApprovalStore.get_pending_approval",
        fake_get_pending,
    )
    monkeypatch.setattr(
        "orchestration.interrupts.approval_store.ApprovalStore.record_approval",
        fake_record,
    )
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

    assert response.status_code == 200
    assert response.json()["approved"] is True
