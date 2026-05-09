from __future__ import annotations


def map_action_to_tool(action: str) -> tuple[str, dict]:
    normalized = action.lower().strip()
    if normalized == "rollback deployment":
        return "rollback_deployment", {"service": "payment-api"}
    if normalized.startswith("restart "):
        return "restart_service", {"service": normalized.removeprefix("restart ").strip()}
    if normalized.startswith("scale "):
        service = normalized.removeprefix("scale ").strip()
        return "scale_service", {"service": service, "replicas": 4}
    return "restart_service", {"service": "payment-api"}
