def map_action_to_category(action: str) -> str:
    normalized = action.lower()
    if "rollback" in normalized:
        return "deployment_rollback"
    if "restart" in normalized:
        return "service_restart"
    if "scale" in normalized:
        return "scaling"
    if "cache" in normalized:
        return "cache_operation"
    return "unknown"
