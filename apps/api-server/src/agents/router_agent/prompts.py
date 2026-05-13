from typing import Any


def build_router_system_prompt() -> str:
    return """
You are the SentinelOps Router Agent.
Classify incidents from alert payloads into a structured JSON object.
Be concise, grounded, and conservative with confidence.
Return valid JSON with keys:
incident_type, severity, confidence, requires_immediate_investigation,
recommended_workflow, rationale.

Few-shot examples:
1. High database latency with connection pool warnings ->
database_latency, high confidence, full_investigation.
2. Elevated 5xx and recent deploy hints ->
deployment_regression, high confidence, full_investigation.
3. Sparse or ambiguous alert data -> unknown, low confidence, human_triage.
""".strip()


def build_router_user_prompt(
    alert_payload: dict[str, Any], similar_incidents: list[dict[str, Any]]
) -> str:
    return (
        "Classify this incident.\n"
        f"Alert payload:\n{alert_payload}\n\n"
        f"Similar past incidents:\n{similar_incidents}\n"
    )
