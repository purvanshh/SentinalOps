from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import yaml
from core.config import get_settings
from db.repositories.audit_repo import AuditLogRepository
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession


class ExecutionGuardError(RuntimeError):
    """Raised when a tool execution request violates safety policy."""


def create_approval_token(
    *,
    incident_id: str,
    action_ids: list[str],
    approved_by: str,
    expires_at,
) -> str:
    settings = get_settings()
    payload = {
        "jti": str(uuid.uuid4()),
        "incident_id": incident_id,
        "action_ids": action_ids,
        "approved_by": approved_by,
        "exp": expires_at,
    }
    secret = settings.approval_token_secret
    secret_str = secret.get_secret_value() if hasattr(secret, "get_secret_value") else secret
    return jwt.encode(payload, secret_str, algorithm="HS256")


def decode_approval_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        secret = settings.approval_token_secret
        secret_str = secret.get_secret_value() if hasattr(secret, "get_secret_value") else secret
        return jwt.decode(token, secret_str, algorithms=["HS256"])
    except JWTError as exc:  # noqa: PERF203
        raise ExecutionGuardError("Invalid approval token") from exc


def load_tool_allowlist() -> dict[str, Any]:
    settings = get_settings()
    path = Path(settings.tool_allowlist_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.exists():
        return {"dangerous_tools": []}
    payload = yaml.safe_load(path.read_text()) or {}
    return payload


async def enforce_tool_execution_policy(
    *,
    tool_name: str,
    safety_level: str,
    context: dict[str, Any],
    session: AsyncSession | None,
) -> None:
    allowlist = load_tool_allowlist()
    incident_id = context.get("incident_id")
    actor_id = context.get("actor_id")
    audit_repo = AuditLogRepository(session) if session is not None else None

    allowed_tools = set(allowlist.get("dangerous_tools", [])) | set(
        allowlist.get("approval_required_tools", [])
    )
    if tool_name not in allowed_tools and safety_level != "read_only":
        if audit_repo is not None:
            await audit_repo.create_event(
                event_type="tool_execution_blocked",
                target=tool_name,
                outcome="blocked_allowlist",
                incident_id=incident_id,
                actor_id=actor_id,
                details=context,
            )
        try:
            from observability.metrics import observe_execution_guard_block

            observe_execution_guard_block("not_allowlisted")
        except Exception:  # noqa: BLE001
            pass
        raise ExecutionGuardError(f"Tool `{tool_name}` is not allowlisted")

    if safety_level == "dangerous":
        token = context.get("approval_token")
        if not token:
            try:
                from observability.metrics import observe_execution_guard_block

                observe_execution_guard_block("no_approval_token")
            except Exception:  # noqa: BLE001
                pass
            raise ExecutionGuardError(f"Tool `{tool_name}` requires an approval token")
        payload = decode_approval_token(token)
        if str(payload.get("incident_id")) != str(incident_id):
            try:
                from observability.metrics import observe_execution_guard_block

                observe_execution_guard_block("incident_mismatch")
            except Exception:  # noqa: BLE001
                pass
            raise ExecutionGuardError("Approval token incident mismatch")
        approved_tool_names = payload.get("action_ids", [])
        if tool_name not in approved_tool_names:
            try:
                from observability.metrics import observe_execution_guard_block

                observe_execution_guard_block("tool_not_approved")
            except Exception:  # noqa: BLE001
                pass
            raise ExecutionGuardError(f"Tool `{tool_name}` was not approved for this execution")

    if audit_repo is not None:
        await audit_repo.create_event(
            event_type="tool_execution_authorized",
            target=tool_name,
            outcome="authorized",
            incident_id=incident_id,
            actor_id=actor_id,
            details=context,
        )
