from collections.abc import AsyncIterator, Callable

from api.middleware.auth import AuthenticatedUser
from core.security.permissions import has_permission
from db.session import get_db_session
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession


async def get_db() -> AsyncIterator[AsyncSession]:
    async for session in get_db_session():
        yield session


async def get_current_user(request: Request) -> AuthenticatedUser:
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )
    return user


CURRENT_USER_DEPENDENCY = Depends(get_current_user)


def require_role(allowed_roles: list[str]) -> Callable:
    async def dependency(
        user: AuthenticatedUser = CURRENT_USER_DEPENDENCY,
    ) -> AuthenticatedUser:
        if not any(
            any(has_permission(role, required) for role in user.roles) for required in allowed_roles
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {', '.join(allowed_roles)}",
            )
        return user

    return dependency
