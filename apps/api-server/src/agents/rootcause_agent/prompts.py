from typing import Any


def build_rootcause_system_prompt() -> str:
    return """
You are the SentinelOps Root Cause Agent.
Work only from the provided evidence items and pattern hints.
Return strict JSON with keys: status, hypotheses,
strongest_hypothesis_index, investigation_log, recommended_next_steps.
Each hypothesis must cite evidence using item_key values that exist in
the provided evidence set.
Do not invent telemetry, services, or timestamps.
""".strip()


def build_rootcause_user_prompt(
    evidence_items: list[dict[str, Any]],
    pattern_hints: list[dict[str, Any]],
    incident_context: dict[str, Any],
) -> str:
    return (
        "Analyze the likely root cause for this incident.\n"
        f"Incident context:\n{incident_context}\n\n"
        f"Evidence items:\n{evidence_items}\n\n"
        f"Pattern hints:\n{pattern_hints}\n"
    )
