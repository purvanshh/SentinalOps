"""
Security hardening tests.

Proves:
  - JWT decoding (valid, invalid, missing subject, missing roles)
  - RBAC role hierarchy enforcement
  - Approval token round-trip and incident mismatch rejection
  - Execution guard blocks unapproved tools and enforces approval token
  - Error handler does not leak internal exception details in production
  - Production secret validation identifies insecure defaults
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from jose import jwt

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_token(
    *,
    sub: str = "user-001",
    roles: list[str] | None = None,
    exp_delta: timedelta = timedelta(hours=1),
    wrong_secret: bool = False,
    omit_sub: bool = False,
    omit_roles: bool = False,
) -> str:
    from core.config import get_settings

    settings = get_settings()
    payload: dict = {
        "aud": settings.auth0_audience,
        "iss": settings.auth_issuer,
        "exp": datetime.now(timezone.utc) + exp_delta,
    }
    if not omit_sub:
        payload["sub"] = sub
    if not omit_roles:
        payload["roles"] = roles or ["operator"]
    secret = "wrong-secret-xyz" if wrong_secret else settings.auth0_secret_key
    algorithm = settings.auth0_algorithms.split(",")[0].strip()
    return jwt.encode(payload, secret, algorithm=algorithm)


# ---------------------------------------------------------------------------
# JWT decoding — valid path
# ---------------------------------------------------------------------------


def test_valid_jwt_decodes_to_authenticated_user():
    from api.middleware.auth import decode_access_token

    token = _make_token(sub="alice", roles=["operator"])
    user = decode_access_token(token)

    assert user.user_id == "alice"
    assert "operator" in user.roles


def test_valid_jwt_with_multiple_roles():
    from api.middleware.auth import decode_access_token

    token = _make_token(roles=["admin", "operator", "viewer"])
    user = decode_access_token(token)

    assert set(user.roles) == {"admin", "operator", "viewer"}


# ---------------------------------------------------------------------------
# JWT decoding — failure paths
# ---------------------------------------------------------------------------


def test_wrong_secret_raises_401():
    from api.middleware.auth import decode_access_token

    token = _make_token(wrong_secret=True)
    with pytest.raises(HTTPException) as exc_info:
        decode_access_token(token)

    assert exc_info.value.status_code == 401


def test_missing_sub_raises_401():
    from api.middleware.auth import decode_access_token

    token = _make_token(omit_sub=True)
    with pytest.raises(HTTPException) as exc_info:
        decode_access_token(token)
    assert exc_info.value.status_code == 401


def test_missing_roles_raises_403():
    from api.middleware.auth import decode_access_token

    token = _make_token(omit_roles=True)
    with pytest.raises(HTTPException) as exc_info:
        decode_access_token(token)
    assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# RBAC role hierarchy
# ---------------------------------------------------------------------------


def test_admin_has_all_permissions():
    from core.security.permissions import has_permission

    assert has_permission("admin", "viewer") is True
    assert has_permission("admin", "operator") is True
    assert has_permission("admin", "admin") is True


def test_operator_has_operator_and_viewer_but_not_admin():
    from core.security.permissions import has_permission

    assert has_permission("operator", "viewer") is True
    assert has_permission("operator", "operator") is True
    assert has_permission("operator", "admin") is False


def test_viewer_has_only_viewer():
    from core.security.permissions import has_permission

    assert has_permission("viewer", "viewer") is True
    assert has_permission("viewer", "operator") is False
    assert has_permission("viewer", "admin") is False


def test_unknown_role_has_no_permissions():
    from core.security.permissions import has_permission

    assert has_permission("unknown_role", "viewer") is False
    assert has_permission("unknown_role", "operator") is False


# ---------------------------------------------------------------------------
# Approval token
# ---------------------------------------------------------------------------


def test_approval_token_round_trip():
    from tools.execution_guard import create_approval_token, decode_approval_token

    incident_id = str(uuid4())
    token = create_approval_token(
        incident_id=incident_id,
        action_ids=["scale_deployment", "restart_pod"],
        approved_by="operator-1",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    payload = decode_approval_token(token)

    assert payload["incident_id"] == incident_id
    assert "scale_deployment" in payload["action_ids"]
    assert payload["approved_by"] == "operator-1"


def test_approval_token_with_wrong_secret_raises_guard_error():
    from tools.execution_guard import ExecutionGuardError

    bad_token = jwt.encode({"incident_id": "x"}, "wrong-secret", algorithm="HS256")

    from tools.execution_guard import decode_approval_token

    with pytest.raises(ExecutionGuardError):
        decode_approval_token(bad_token)


# ---------------------------------------------------------------------------
# Execution guard — tool allowlist and approval enforcement
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execution_guard_blocks_tool_not_in_allowlist(monkeypatch, tmp_path):
    import yaml
    from tools.execution_guard import enforce_tool_execution_policy

    allowlist_file = tmp_path / "allowlist.yaml"
    allowlist_file.write_text(yaml.dump({"dangerous_tools": ["scale_deployment"]}))
    monkeypatch.setattr(
        "tools.execution_guard.load_tool_allowlist",
        lambda: {"dangerous_tools": ["scale_deployment"]},
    )

    from tools.execution_guard import ExecutionGuardError

    with pytest.raises(ExecutionGuardError, match="not allowlisted"):
        await enforce_tool_execution_policy(
            tool_name="drop_database",
            safety_level="dangerous",
            context={"incident_id": str(uuid4()), "actor_id": "op-1"},
            session=None,
        )


@pytest.mark.asyncio
async def test_execution_guard_blocks_dangerous_tool_without_approval_token(monkeypatch):
    from tools.execution_guard import ExecutionGuardError, enforce_tool_execution_policy

    monkeypatch.setattr(
        "tools.execution_guard.load_tool_allowlist",
        lambda: {"dangerous_tools": ["scale_deployment"]},
    )

    with pytest.raises(ExecutionGuardError, match="requires an approval token"):
        await enforce_tool_execution_policy(
            tool_name="scale_deployment",
            safety_level="dangerous",
            context={"incident_id": str(uuid4()), "actor_id": "op-1"},
            session=None,
        )


@pytest.mark.asyncio
async def test_execution_guard_blocks_token_with_incident_mismatch(monkeypatch):
    from tools.execution_guard import (
        ExecutionGuardError,
        create_approval_token,
        enforce_tool_execution_policy,
    )

    monkeypatch.setattr(
        "tools.execution_guard.load_tool_allowlist",
        lambda: {"dangerous_tools": ["scale_deployment"]},
    )

    real_incident = str(uuid4())
    other_incident = str(uuid4())
    token = create_approval_token(
        incident_id=other_incident,
        action_ids=["scale_deployment"],
        approved_by="op-1",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )

    with pytest.raises(ExecutionGuardError, match="incident mismatch"):
        await enforce_tool_execution_policy(
            tool_name="scale_deployment",
            safety_level="dangerous",
            context={"incident_id": real_incident, "actor_id": "op-1", "approval_token": token},
            session=None,
        )


# ---------------------------------------------------------------------------
# Error handler — no internal detail leak in production
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_error_handler_omits_error_detail_in_production(monkeypatch):
    from api.middleware.error_handler import unhandled_exception_handler

    monkeypatch.setattr(
        "api.middleware.error_handler.get_settings",
        lambda: MagicMock(is_production=True),
    )

    mock_request = MagicMock()
    mock_request.url.path = "/test"
    mock_request.method = "GET"

    response = await unhandled_exception_handler(
        mock_request, RuntimeError("secret DB password leaked")
    )
    body = response.body.decode()

    assert "secret DB password leaked" not in body
    assert "Internal server error" in body


@pytest.mark.asyncio
async def test_error_handler_includes_error_detail_in_development(monkeypatch):
    from api.middleware.error_handler import unhandled_exception_handler

    monkeypatch.setattr(
        "api.middleware.error_handler.get_settings",
        lambda: MagicMock(is_production=False),
    )

    mock_request = MagicMock()
    mock_request.url.path = "/test"
    mock_request.method = "GET"

    response = await unhandled_exception_handler(mock_request, ValueError("debug info"))
    body = response.body.decode()

    assert "debug info" in body


# ---------------------------------------------------------------------------
# Production secret validation
# ---------------------------------------------------------------------------


def test_production_secret_validation_catches_default_secrets():
    from core.config import Settings

    settings = Settings(
        app_env="production",
        auth0_secret_key="dev-secret-change-me",
        approval_token_secret="approval-secret-change-me",
    )
    issues = settings.validate_production_secrets()

    assert len(issues) == 2
    assert any("AUTH0_SECRET_KEY" in i for i in issues)
    assert any("APPROVAL_TOKEN_SECRET" in i for i in issues)


def test_production_secret_validation_passes_with_real_secrets():
    from core.config import Settings

    settings = Settings(
        app_env="production",
        auth0_secret_key="super-secret-prod-key-abc123",
        approval_token_secret="another-real-secret-xyz456",
    )
    assert settings.validate_production_secrets() == []


def test_secret_validation_skipped_in_development():
    from core.config import Settings

    settings = Settings(
        app_env="development",
        auth0_secret_key="dev-secret-change-me",
    )
    assert settings.validate_production_secrets() == []
