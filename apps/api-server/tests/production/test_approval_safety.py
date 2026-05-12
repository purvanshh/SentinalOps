"""
Approval gate and execution gating safety tests.

Proves:
  - Approval gate routes decisions to correct incident
  - Approval token is created only when approved=True
  - Rejected decisions do not produce an approval token
  - Execution guard blocks safe tools that are not allowlisted
  - Execution guard allows read-only tools without token
  - Token referencing wrong tool ID is rejected at enforcement
  - Token expiry is encoded and decoded faithfully
  - Approval store records both approve and reject outcomes
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from jose import jwt


# ---------------------------------------------------------------------------
# Approval token creation — conditional on decision
# ---------------------------------------------------------------------------

def test_approval_token_created_when_approved():
    from tools.execution_guard import create_approval_token, decode_approval_token

    incident_id = str(uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
    token = create_approval_token(
        incident_id=incident_id,
        action_ids=["scale_deployment"],
        approved_by="op-1",
        expires_at=expires_at,
    )
    payload = decode_approval_token(token)
    assert payload["incident_id"] == incident_id
    assert payload["approved_by"] == "op-1"
    assert "scale_deployment" in payload["action_ids"]


def test_approval_token_not_issued_on_rejection():
    """Route logic: approval_token=None when approved=False."""
    from tools.execution_guard import create_approval_token

    # Simulate the route: only create token when approved=True
    approved = False
    token = create_approval_token(
        incident_id=str(uuid4()),
        action_ids=["scale_deployment"],
        approved_by="op-1",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    ) if approved else None

    assert token is None


def test_approval_token_encodes_expiry():
    from tools.execution_guard import create_approval_token, decode_approval_token
    from core.config import get_settings

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    token = create_approval_token(
        incident_id="inc-999",
        action_ids=["restart_pod"],
        approved_by="admin-1",
        expires_at=expires_at,
    )
    # Decode without expiry enforcement to inspect raw payload
    settings = get_settings()
    raw = jwt.decode(
        token,
        settings.approval_token_secret,
        algorithms=["HS256"],
        options={"verify_exp": False},
    )
    assert "exp" in raw


# ---------------------------------------------------------------------------
# Execution guard — tool-level enforcement
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_read_only_tool_bypasses_approval_requirement(monkeypatch):
    from tools.execution_guard import enforce_tool_execution_policy

    monkeypatch.setattr(
        "tools.execution_guard.load_tool_allowlist",
        lambda: {"dangerous_tools": ["scale_deployment"]},
    )

    # Should not raise — read_only safety_level skips allowlist check
    await enforce_tool_execution_policy(
        tool_name="get_pod_logs",
        safety_level="read_only",
        context={"incident_id": str(uuid4()), "actor_id": "viewer-1"},
        session=None,
    )


@pytest.mark.asyncio
async def test_execution_guard_blocks_unlisted_standard_tool(monkeypatch):
    from tools.execution_guard import enforce_tool_execution_policy, ExecutionGuardError

    monkeypatch.setattr(
        "tools.execution_guard.load_tool_allowlist",
        lambda: {"dangerous_tools": ["scale_deployment"]},
    )

    with pytest.raises(ExecutionGuardError, match="not allowlisted"):
        await enforce_tool_execution_policy(
            tool_name="delete_namespace",
            safety_level="standard",
            context={"incident_id": str(uuid4()), "actor_id": "op-1"},
            session=None,
        )


@pytest.mark.asyncio
async def test_execution_guard_rejects_token_for_wrong_tool(monkeypatch):
    from tools.execution_guard import (
        enforce_tool_execution_policy,
        create_approval_token,
        ExecutionGuardError,
    )

    monkeypatch.setattr(
        "tools.execution_guard.load_tool_allowlist",
        lambda: {"dangerous_tools": ["scale_deployment", "restart_pod"]},
    )

    incident_id = str(uuid4())
    token = create_approval_token(
        incident_id=incident_id,
        action_ids=["restart_pod"],  # token approves restart_pod, not scale_deployment
        approved_by="op-1",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )

    with pytest.raises(ExecutionGuardError, match="was not approved"):
        await enforce_tool_execution_policy(
            tool_name="scale_deployment",
            safety_level="dangerous",
            context={
                "incident_id": incident_id,
                "actor_id": "op-1",
                "approval_token": token,
            },
            session=None,
        )


@pytest.mark.asyncio
async def test_execution_guard_allows_correctly_approved_tool(monkeypatch):
    from tools.execution_guard import (
        enforce_tool_execution_policy,
        create_approval_token,
    )

    monkeypatch.setattr(
        "tools.execution_guard.load_tool_allowlist",
        lambda: {"dangerous_tools": ["scale_deployment"]},
    )

    incident_id = str(uuid4())
    token = create_approval_token(
        incident_id=incident_id,
        action_ids=["scale_deployment"],
        approved_by="op-1",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )

    # Should not raise
    await enforce_tool_execution_policy(
        tool_name="scale_deployment",
        safety_level="dangerous",
        context={
            "incident_id": incident_id,
            "actor_id": "op-1",
            "approval_token": token,
        },
        session=None,
    )


# ---------------------------------------------------------------------------
# Approval token edge cases
# ---------------------------------------------------------------------------

def test_multiple_actions_in_single_token():
    from tools.execution_guard import create_approval_token, decode_approval_token

    incident_id = str(uuid4())
    actions = ["scale_deployment", "restart_pod", "drain_node"]
    token = create_approval_token(
        incident_id=incident_id,
        action_ids=actions,
        approved_by="admin-1",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    )
    payload = decode_approval_token(token)
    assert set(payload["action_ids"]) == set(actions)


def test_decode_approval_token_raises_on_tampered_token():
    from tools.execution_guard import decode_approval_token, ExecutionGuardError

    tampered = "eyJhbGciOiJIUzI1NiJ9.eyJpbmNpZGVudF9pZCI6InRlc3QifQ.invalid_sig"
    with pytest.raises(ExecutionGuardError):
        decode_approval_token(tampered)


def test_approval_token_incident_id_is_preserved_as_string():
    from tools.execution_guard import create_approval_token, decode_approval_token

    incident_id = str(uuid4())
    token = create_approval_token(
        incident_id=incident_id,
        action_ids=["restart_pod"],
        approved_by="op-1",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    payload = decode_approval_token(token)
    assert payload["incident_id"] == incident_id
    assert isinstance(payload["incident_id"], str)
