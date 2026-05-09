from __future__ import annotations

from typing import Any


def build_structured_timeline(executions: list[Any], remediation_actions: list[Any]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for execution in executions:
        items.append(
            {
                "time": execution.created_at.isoformat() if execution.created_at else "unknown",
                "event": f"{execution.agent_name} completed",
                "source": execution.agent_name,
                "impact": execution.status,
                "mitigation": "",
            }
        )
    for action in remediation_actions:
        items.append(
            {
                "time": action.updated_at.isoformat() if action.updated_at else "unknown",
                "event": action.action,
                "source": "remediation_action",
                "impact": action.status,
                "mitigation": action.details.get("approval_note", "") if action.details else "",
            }
        )
    items.sort(key=lambda item: item["time"])
    return items


def render_timeline_markdown(timeline: list[dict[str, str]]) -> str:
    if not timeline:
        return "- No workflow events recorded."
    lines = ["| Time (UTC) | Event | Source | Impact | Mitigation |", "| --- | --- | --- | --- | --- |"]
    for item in timeline:
        lines.append(
            f"| {item['time']} | {item['event']} | {item['source']} | {item['impact']} | {item['mitigation']} |"
        )
    return "\n".join(lines)
