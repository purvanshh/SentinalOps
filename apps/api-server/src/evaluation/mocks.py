from __future__ import annotations

from typing import Any


def build_mock_context(dataset: dict[str, Any]) -> dict[str, Any]:
    return {
        "alert_payload": dataset["alert_payload"],
        "router": dataset["mocked_tool_responses"].get("router", {}),
        "metrics": dataset["mocked_tool_responses"].get("metrics", {}),
        "logs": dataset["mocked_tool_responses"].get("logs", {}),
        "deployment": dataset["mocked_tool_responses"].get("deployment", {}),
        "topology": dataset["mocked_tool_responses"].get("topology", {}),
    }
