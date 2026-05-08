from typing import Any


def build_logs_system_prompt() -> str:
    return """
You are the SentinelOps Logs Agent.
Use Loki tools to find error signatures, stack traces, and temporal correlations.
Return strict JSON with keys: error_signatures and temporal_correlations.
Keep every statement grounded in the tool output.
""".strip()


def build_logs_user_prompt(context: dict[str, Any]) -> str:
    return (
        "Investigate this incident using logs.\n"
        f"Context:\n{context}\n"
        "Search for recurring failures, stack traces, and timing correlations."
    )
