ROLE_LEVELS = {"viewer": 1, "operator": 2, "admin": 3}


def has_permission(role: str, required_role: str) -> bool:
    return ROLE_LEVELS.get(role, 0) >= ROLE_LEVELS.get(required_role, 99)
