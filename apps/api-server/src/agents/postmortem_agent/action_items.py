from typing import Any


def _similarity(left: str, right: str) -> float:
    left_tokens = set(left.lower().split())
    right_tokens = set(right.lower().split())
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def propose_action_items(
    *,
    root_cause: dict[str, Any],
    contributing_factors: list[dict[str, Any]],
    existing_items: list[dict[str, Any]],
    incident_id,
) -> list[dict[str, Any]]:
    existing_titles = [item["title"] for item in existing_items]
    proposals: list[dict[str, Any]] = []

    candidate_titles = []
    if "deployment" in str(root_cause).lower():
        candidate_titles.append("Add deployment guardrails for payment-api")
    if "pool" in str(root_cause).lower() or "latency" in str(root_cause).lower():
        candidate_titles.append("Add connection pool saturation alerting")
    if any(factor["detected"] for factor in contributing_factors):
        candidate_titles.append("Expand runbook coverage for recurring incident patterns")

    for title in candidate_titles:
        if any(_similarity(title, existing) >= 0.7 for existing in existing_titles):
            continue
        proposals.append(
            {
                "incident_id": incident_id,
                "title": title,
                "description": f"Prevent recurrence by addressing: {title}.",
                "status": "open",
                "completed": False,
            }
        )
    return proposals
