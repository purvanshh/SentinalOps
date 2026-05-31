from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from core.config import get_settings
from core.security.permissions import has_permission
from fastapi import HTTPException, Request, status
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


@dataclass(slots=True)
class AuthenticatedUser:
    user_id: str
    roles: list[str]
    token_payload: dict[str, Any]


def _extract_roles(payload: dict[str, Any]) -> list[str]:
    roles = payload.get("roles") or payload.get("permissions") or []
    if isinstance(roles, str):
        roles = roles.split()
    if not isinstance(roles, list):
        return []
    return [str(role) for role in roles]


def decode_access_token(token: str) -> AuthenticatedUser:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.auth0_secret_key.get_secret_value() if hasattr(settings.auth0_secret_key, 'get_secret_value') else settings.auth0_secret_key,
            algorithms=[
                algorithm.strip()
                for algorithm in settings.auth0_algorithms.split(",")
                if algorithm.strip()
            ],
            audience=settings.auth0_audience,
            issuer=settings.auth_issuer,
            options={"require_exp": True, "verify_exp": True, "verify_aud": True},
        )
    except JWTError as exc:  # noqa: PERF203
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token"
        ) from exc

    # Explicit aud check — some jose versions don't raise when aud is missing
    if settings.auth0_audience and payload.get("aud") != settings.auth0_audience:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")

    user_id = str(payload.get("sub") or "")
    roles = _extract_roles(payload)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing subject"
        )
    if not roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token missing roles")
    return AuthenticatedUser(user_id=user_id, roles=roles, token_payload=payload)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        if request.url.path in {"/", "/health", "/metrics", "/docs", "/openapi.json", "/redoc"}:
            return await call_next(request)

        try:
            header = request.headers.get("authorization", "")
            if not header.startswith("Bearer "):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token"
                )

            token = header.split(" ", 1)[1].strip()
            user = decode_access_token(token)
            request.state.user = user
            request.state.user_id = user.user_id
            request.state.user_roles = user.roles
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

        return await call_next(request)


def require_role(request: Request, required_role: str) -> AuthenticatedUser:
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )
    if not any(has_permission(role, required_role) for role in user.roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Required role `{required_role}` not granted",
        )
    return user
