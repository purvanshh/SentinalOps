from typing import Any


def build_metrics_system_prompt() -> str:
    return """
You are the SentinelOps Metrics Agent.
Use Prometheus tools to inspect CPU, memory, latency, request rate, and dependencies.
Return strict JSON with keys: summary, anomalies, correlation_hints, raw_query_links.
Keep the analysis factual and concise.
""".strip()


def build_metrics_user_prompt(context: dict[str, Any]) -> str:
    return (
        "Investigate this incident using Prometheus.\n"
        f"Context:\n{context}\n"
        "Query the service metrics around the alert window and summarize anomalies."
    )
