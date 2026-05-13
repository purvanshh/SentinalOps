from collections.abc import Iterable
from typing import Any

from db.models.agent_execution import AgentExecution


def normalize_agent_executions(executions: Iterable[AgentExecution]) -> list[dict[str, Any]]:
    evidence_items: list[dict[str, Any]] = []
    for execution in executions:
        output = execution.output or {}
        created_at = execution.created_at.isoformat() if execution.created_at else None
        if execution.agent_name == "metrics_agent":
            for index, anomaly in enumerate(output.get("anomalies", []), start=1):
                evidence_items.append(
                    {
                        "source": "metrics_agent",
                        "item_type": "metric_anomaly",
                        "item_key": f"MET-{index}",
                        "content": {
                            **anomaly,
                            "timestamp": created_at,
                            "service": execution.input.get("messages", [{}])[-1] if execution.input else None,
                        },
                    }
                )
        elif execution.agent_name == "logs_agent":
            for index, signature in enumerate(output.get("error_signatures", []), start=1):
                evidence_items.append(
                    {
                        "source": "logs_agent",
                        "item_type": "error_signature",
                        "item_key": f"LOG-{index}",
                        "content": {
                            **signature,
                            "timestamp": created_at,
                        },
                    }
                )
        elif execution.agent_name == "deployment_agent":
            for index, change in enumerate(output.get("recent_changes", []), start=1):
                evidence_items.append(
                    {
                        "source": "deployment_agent",
                        "item_type": "deployment_change",
                        "item_key": f"DEP-{index}",
                        "content": {
                            **change,
                            "timestamp": change.get("time", created_at),
                            "commit_sha": change.get("commit_sha", ""),
                            "commit_author": change.get("commit_author", ""),
                            "files_changed": change.get("files_changed", []),
                        },
                    }
                )
    return evidence_items
