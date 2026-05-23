from typing import Any


def evaluate_contributing_factors(context: dict[str, Any]) -> list[dict[str, str | bool]]:
    deployment = context.get("deployment", {})
    metrics = context.get("metrics", {})
    logs = context.get("logs", {})
    deploy_detected = bool(deployment.get("recent_changes"))
    high_latency = "latency" in metrics.get("summary", "").lower()
    recurring_errors = bool(logs.get("error_signatures"))
    factors = [
        {
            "factor": "Deployment procedure risk",
            "detected": deploy_detected,
            "detail": deployment.get(
                "correlation_with_incident", "No deployment correlation found."
            ),
        },
        {
            "factor": "Monitoring lag",
            "detected": high_latency,
            "detail": (
                "Alert and anomaly windows indicate whether detection lagged the first symptom."
            ),
        },
        {
            "factor": "Recurring error signatures",
            "detected": recurring_errors,
            "detail": "Repeated log signatures suggest unresolved latent failure modes.",
        },
        {
            "factor": "Insufficient redundancy",
            "detected": deploy_detected and recurring_errors,
            "detail": (
                "Service degradation after a single change suggests weak "
                "safety rails or fallback capacity."
            ),
        },
    ]
    return factors
