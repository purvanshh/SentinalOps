from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from core.security.permissions import has_permission


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        request.state.user_role = request.headers.get("x-sentinelops-role", "admin")
        request.state.user_id = request.headers.get("x-sentinelops-user", "local-dev")
        return await call_next(request)


def require_role(request: Request, required_role: str) -> None:
    role = getattr(request.state, "user_role", "viewer")
    if not has_permission(role, required_role):
        raise PermissionError(f"Role `{role}` does not satisfy `{required_role}` access.")
