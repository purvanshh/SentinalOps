from typing import Any


def evaluate_contributing_factors(context: dict[str, Any]) -> list[dict[str, str | bool]]:
    deployment = context.get("deployment", {})
    metrics = context.get("metrics", {})
    logs = context.get("logs", {})
    factors = [
        {
            "factor": "Deployment procedure risk",
            "detected": bool(deployment.get("recent_changes")),
            "detail": deployment.get("correlation_with_incident", "No deployment correlation found."),
        },
        {
            "factor": "Monitoring lag",
            "detected": "latency" in metrics.get("summary", "").lower(),
            "detail": "Alert and anomaly windows indicate whether detection lagged the first symptom.",
        },
        {
            "factor": "Recurring error signatures",
            "detected": bool(logs.get("error_signatures")),
            "detail": "Repeated log signatures suggest unresolved latent failure modes.",
        },
    ]
    return factors
