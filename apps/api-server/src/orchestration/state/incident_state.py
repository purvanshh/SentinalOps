from typing import Any, TypedDict


class IncidentState(TypedDict, total=False):
    incident_id: str
    thread_id: str
    status: str
    router: dict[str, Any]
    metrics: dict[str, Any]
    logs: dict[str, Any]
    deployment: dict[str, Any]
    root_cause: dict[str, Any]
    risk: dict[str, Any]
    remediation: dict[str, Any]
    approval: dict[str, Any]
    execution: dict[str, Any]
