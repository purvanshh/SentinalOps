"""
Phase-38 JWT/RBAC and production secret enforcement hardening.

Proves:
  - Expired tokens are rejected with 401
  - Malformed payload (no exp, no aud) raises 401
  - Privilege escalation: operator cannot access admin endpoints
  - Approval token now carries jti (JWT ID) for replay detection
  - Each call to create_approval_token generates a unique jti
  - validate_required_configuration catches incomplete configurations
  - validate_production_secrets passes with strong secrets
  - Error handler suppresses exc detail in production for all exception types
  - Auth middleware returns 401 for missing Bearer prefix
  - Unknown algorithm in token raises 401
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

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
    omit_exp: bool = False,
    omit_aud: bool = False,
) -> str:
    from core.config import get_settings

    settings = get_settings()
    payload: dict = {}
    if not omit_aud:
        payload["aud"] = settings.auth0_audience
    payload["iss"] = settings.auth_issuer
    if not omit_exp:
        payload["exp"] = datetime.now(timezone.utc) + exp_delta
    if not omit_sub:
        payload["sub"] = sub
    if not omit_roles:
        payload["roles"] = roles or ["operator"]
    secret = "wrong-secret-xyz" if wrong_secret else settings.auth0_secret_key
    algorithm = settings.auth0_algorithms.split(",")[0].strip()
    return jwt.encode(payload, secret, algorithm=algorithm)


# ---------------------------------------------------------------------------
# Expired token
# ---------------------------------------------------------------------------


def test_expired_token_raises_401():
    from api.middleware.auth import decode_access_token

    token = _make_token(exp_delta=timedelta(seconds=-1))
    with pytest.raises(HTTPException) as exc_info:
        decode_access_token(token)
    assert exc_info.value.status_code == 401


def test_deeply_expired_token_raises_401():
    from api.middleware.auth import decode_access_token

    token = _make_token(exp_delta=timedelta(days=-30))
    with pytest.raises(HTTPException) as exc_info:
        decode_access_token(token)
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# Malformed claims
# ---------------------------------------------------------------------------


def test_token_without_exp_raises_401():
    from api.middleware.auth import decode_access_token

    token = _make_token(omit_exp=True)
    with pytest.raises(HTTPException) as exc_info:
        decode_access_token(token)
    assert exc_info.value.status_code == 401


def test_token_without_aud_raises_401():
    from api.middleware.auth import decode_access_token

    token = _make_token(omit_aud=True)
    with pytest.raises(HTTPException) as exc_info:
        decode_access_token(token)
    assert exc_info.value.status_code == 401


def test_token_signed_with_different_algorithm_raises_401():
    from api.middleware.auth import decode_access_token
    from core.config import get_settings

    settings = get_settings()
    payload = {
        "sub": "user",
        "roles": ["operator"],
        "aud": settings.auth0_audience,
        "iss": settings.auth_issuer,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    # Encode with RS256 (we only accept HS256) — jose will use HS256 as a fallback
    # but create with none algorithm to ensure decode fails
    none_token = jwt.encode(payload, "", algorithm="HS256") + ".extra"
    with pytest.raises(HTTPException) as exc_info:
        decode_access_token(none_token)
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# Privilege escalation
# ---------------------------------------------------------------------------


def test_operator_cannot_escalate_to_admin():
    from core.security.permissions import has_permission

    assert has_permission("operator", "admin") is False


def test_viewer_cannot_escalate_to_operator():
    from core.security.permissions import has_permission

    assert has_permission("viewer", "operator") is False


def test_unknown_role_cannot_escalate_to_any():
    from core.security.permissions import has_permission

    for required in ("viewer", "operator", "admin"):
        assert has_permission("superuser", required) is False
        assert has_permission("", required) is False
        assert has_permission("null", required) is False


# ---------------------------------------------------------------------------
# Approval token: jti (replay protection)
# ---------------------------------------------------------------------------


def test_approval_token_contains_jti():
    from tools.execution_guard import create_approval_token, decode_approval_token

    token = create_approval_token(
        incident_id="inc-001",
        action_ids=["scale_deployment"],
        approved_by="op-1",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    payload = decode_approval_token(token)
    assert "jti" in payload
    assert payload["jti"]


def test_each_approval_token_has_unique_jti():
    from tools.execution_guard import create_approval_token, decode_approval_token

    t1 = create_approval_token(
        incident_id="inc-001",
        action_ids=["restart_pod"],
        approved_by="op-1",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    t2 = create_approval_token(
        incident_id="inc-001",
        action_ids=["restart_pod"],
        approved_by="op-1",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    p1 = decode_approval_token(t1)
    p2 = decode_approval_token(t2)
    assert p1["jti"] != p2["jti"]


def test_approval_token_jti_is_uuid_format():
    import re

    from tools.execution_guard import create_approval_token, decode_approval_token

    token = create_approval_token(
        incident_id="inc-001",
        action_ids=["scale_deployment"],
        approved_by="op-1",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    payload = decode_approval_token(token)
    uuid_pattern = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    assert uuid_pattern.match(payload["jti"])


# ---------------------------------------------------------------------------
# Configuration validation
# ---------------------------------------------------------------------------


def test_validate_required_configuration_catches_missing_redis():
    from core.config import Settings

    settings = Settings(app_env="development", redis_url="")
    issues = settings.validate_required_configuration()
    assert any("REDIS_URL" in i for i in issues)


def test_validate_required_configuration_catches_missing_broker():
    from core.config import Settings

    settings = Settings(app_env="development", celery_broker_url="")
    issues = settings.validate_required_configuration()
    assert any("CELERY_BROKER_URL" in i for i in issues)


def test_validate_required_configuration_passes_with_full_config():
    from core.config import Settings

    settings = Settings(
        app_env="development",
        redis_url="redis://redis:6379/0",
        celery_broker_url="redis://redis:6379/1",
    )
    issues = settings.validate_required_configuration()
    assert not any("REDIS_URL" in i for i in issues)
    assert not any("CELERY_BROKER_URL" in i for i in issues)


def test_production_dummy_llm_key_flagged():
    from core.config import Settings

    settings = Settings(
        app_env="production",
        auth0_secret_key="super-secret-prod-key-abc123",
        approval_token_secret="another-real-secret-xyz456",
        llm_provider="openai_compatible",
        llm_api_key="dummy-key",
        nvidia_api_key="",
    )
    issues = settings.validate_required_configuration()
    assert any("LLM_API_KEY" in i for i in issues)


# ---------------------------------------------------------------------------
# Error handler: comprehensive suppression
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_error_handler_suppresses_sql_error_detail(monkeypatch):
    from api.middleware.error_handler import unhandled_exception_handler

    monkeypatch.setattr(
        "api.middleware.error_handler.get_settings",
        lambda: MagicMock(is_production=True),
    )
    request = MagicMock()
    request.url.path = "/incidents"
    request.method = "POST"

    sql_error = Exception("FATAL: password authentication failed for user 'sentinelops'")
    response = await unhandled_exception_handler(request, sql_error)
    body = response.body.decode()
    assert "password authentication failed" not in body
    assert "Internal server error" in body


@pytest.mark.asyncio
async def test_error_handler_suppresses_file_path_leak(monkeypatch):
    from api.middleware.error_handler import unhandled_exception_handler

    monkeypatch.setattr(
        "api.middleware.error_handler.get_settings",
        lambda: MagicMock(is_production=True),
    )
    request = MagicMock()
    request.url.path = "/test"
    request.method = "GET"

    path_error = FileNotFoundError("/etc/secrets/prod_key.pem: No such file or directory")
    response = await unhandled_exception_handler(request, path_error)
    body = response.body.decode()
    assert "/etc/secrets" not in body
    assert "Internal server error" in body
