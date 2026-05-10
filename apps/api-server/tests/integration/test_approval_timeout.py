from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from workers.schedulers.approval_timeout import check_pending_approvals


def test_check_pending_approvals_escalates_and_auto_rejects(monkeypatch) -> None:
    now = datetime.now(UTC)
    rows = [
        SimpleNamespace(
            incident_id="incident-escalate",
            created_at=now - timedelta(minutes=20),
            expires_at=(now - timedelta(minutes=5)).isoformat(),
        ),
        SimpleNamespace(
            incident_id="incident-reject",
            created_at=now - timedelta(minutes=40),
            expires_at=(now - timedelta(minutes=20)).isoformat(),
        ),
    ]
    dispatched = []

    class _FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

    class _FakeApprovalStore:
        def __init__(self, _session):
            pass

        async def list_pending_approvals(self):
            return rows

    monkeypatch.setattr(
        "workers.schedulers.approval_timeout.get_settings",
        lambda: SimpleNamespace(approval_timeout_minutes=15, approval_auto_reject_minutes=30),
    )
    monkeypatch.setattr("workers.schedulers.approval_timeout.SessionLocal", lambda: _FakeSession())
    monkeypatch.setattr("workers.schedulers.approval_timeout.ApprovalStore", _FakeApprovalStore)
    monkeypatch.setattr(
        "workers.schedulers.approval_timeout.escalate_approval.delay",
        lambda incident_id: dispatched.append(incident_id),
    )

    result = asyncio.run(check_pending_approvals())

    assert "incident-escalate:escalated" in result
    assert "incident-reject:auto_reject" in result
    assert dispatched == ["incident-escalate", "incident-reject"]
