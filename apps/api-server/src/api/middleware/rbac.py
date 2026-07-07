from functools import wraps

from fastapi import HTTPException, Request, status


def requires_permission(permission: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request = next((arg for arg in args if isinstance(arg, Request)), None)
            if not request:
                for _k, v in kwargs.items():
                    if isinstance(v, Request):
                        request = v
                        break
            if not request:
                return await func(*args, **kwargs)

            user = getattr(request.state, "user", None)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
                )

            role_permissions = {
                "viewer": ["incident:read", "config:read"],
                "operator": [
                    "incident:read",
                    "incident:write",
                    "approval:approve",
                    "approval:reject",
                    "execution:trigger",
                    "config:read",
                ],
                "admin": ["*"],
            }

            has_perm = False
            for role in user.roles:
                perms = role_permissions.get(role, [])
                if "*" in perms or permission in perms:
                    has_perm = True
                    break

            if not has_perm:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied"
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator
