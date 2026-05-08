from typing import Any


def build_deployment_system_prompt() -> str:
    return """
You are the SentinelOps Deployment Agent.
Use deployment tools to inspect recent changes, summarize risky diffs, and correlate them with the incident.
Return strict JSON with keys: recent_changes and correlation_with_incident.
Each recent change must include deployment_id, service, version, time, commit_summary, and risk_score.
""".strip()


def build_deployment_user_prompt(context: dict[str, Any]) -> str:
    return (
        "Investigate recent deployments for this incident.\n"
        f"Context:\n{context}\n"
        "Check recent deployments, fetch the most relevant commit diff, and describe likely correlation."
    )
