from types import SimpleNamespace
from uuid import uuid4

import pytest

from orchestration.nodes.approval_node import approval_node
from orchestration.nodes.execution_node import execution_node


class DummySession:
    async def commit(self) -> None:
        return None


@pytest.mark.asyncio
async def test_approval_node_disables_execution_in_safe_mode() -> None:
    result = await approval_node(
        {
            "incident_id": str(uuid4()),
            "operating_mode": "SAFE_MODE",
            "remediation_plan": {
                "summary": "Fallback plan",
                "steps": [{"action": "restart service", "requires_approval": True}],
            },
        },
        session=DummySession(),
    )

    assert result["status"] == "observe_only"
    assert result["approval"]["execution_disabled"] is True
    assert result["graph_status"] == "observe_only"


@pytest.mark.asyncio
async def test_execution_node_noops_in_safe_mode(monkeypatch) -> None:
    incident = SimpleNamespace(
        id=uuid4(),
        remediation_actions=[],
        status="ready_for_execution",
    )

    async def fake_get_with_context(self, incident_id):
        return incident

    monkeypatch.setattr(
        "db.repositories.incident_repo.IncidentRepository.get_with_context",
        fake_get_with_context,
    )

    result = await execution_node(
        {
            "incident_id": str(incident.id),
            "operating_mode": "SAFE_MODE",
            "approval": {"approved": False},
        },
        session=DummySession(),
    )

    assert result["status"] == "observe_only"
    assert result["execution"]["execution_disabled"] is True
    assert result["graph_status"] == "observe_only"
