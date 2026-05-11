from typing import Annotated, Any, TypedDict


def append_unique(current: list[str], updates: list[str] | None) -> list[str]:
    if not updates:
        return current
    merged = list(current)
    for item in updates:
        if item not in merged:
            merged.append(item)
    return merged


class IncidentState(TypedDict, total=False):
    incident_id: str
    thread_id: str
    execution_id: str
    status: str
    operating_mode: str
    remaining_steps: int
    started_at: float
    alert_payload: dict[str, Any]
    classification: dict[str, Any]
    metrics_summary: dict[str, Any]
    logs_summary: dict[str, Any]
    deployment_summary: dict[str, Any]
    hypotheses: list[dict[str, Any]]
    root_cause: dict[str, Any]
    risk_assessment: dict[str, Any]
    remediation_plan: dict[str, Any]
    approval_request: dict[str, Any]
    approval: dict[str, Any]
    approved_actions: list[str]
    execution: dict[str, Any]
    postmortem: dict[str, Any]
    errors: Annotated[list[str], append_unique]
    completed_nodes: Annotated[list[str], append_unique]
    # Resilience metadata
    provider_chain_result: dict[str, Any]
    fallback_activated: bool
    degraded_mode_activation: dict[str, Any]
