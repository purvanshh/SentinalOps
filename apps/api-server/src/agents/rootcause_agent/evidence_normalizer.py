from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from db.models.agent_execution import AgentExecution


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _confidence_for_metric(anomaly: dict[str, Any]) -> float:
    """Derive a confidence score from the anomaly's deviation magnitude."""
    deviation = anomaly.get("deviation_factor", anomaly.get("deviation", 0.0))
    try:
        magnitude = float(deviation)
    except (TypeError, ValueError):
        return 0.5
    return min(round(0.5 + min(magnitude, 5.0) / 10.0, 2), 1.0)


def _confidence_for_log(signature: dict[str, Any]) -> float:
    """Derive a confidence score from the error count and trace coverage."""
    count = signature.get("count", 0)
    trace_count = len(signature.get("trace_ids", []))
    if count == 0:
        return 0.3
    trace_bonus = min(trace_count * 0.05, 0.2)
    return min(round(0.5 + min(count, 20) / 40.0 + trace_bonus, 2), 1.0)


def _confidence_for_deployment(change: dict[str, Any]) -> float:
    """Derive a confidence score from the deployment risk score and commit provenance."""
    risk = change.get("risk_score", 0.0)
    try:
        risk = float(risk)
    except (TypeError, ValueError):
        risk = 0.0
    has_sha = bool(change.get("commit_sha"))
    has_author = bool(change.get("commit_author"))
    provenance_bonus = 0.1 if (has_sha and has_author) else 0.0
    return min(round(risk * 0.8 + 0.2 + provenance_bonus, 2), 1.0)


def normalize_agent_executions(executions: Iterable[AgentExecution]) -> list[dict[str, Any]]:
    retrieval_timestamp = _now_iso()
    evidence_items: list[dict[str, Any]] = []

    for execution in executions:
        output = execution.output or {}
        created_at = (
            execution.created_at.isoformat() if execution.created_at else retrieval_timestamp
        )

        if execution.agent_name == "metrics_agent":
            for index, anomaly in enumerate(output.get("anomalies", []), start=1):
                evidence_items.append(
                    {
                        "source": "metrics_agent",
                        "item_type": "metric_anomaly",
                        "item_key": f"MET-{index}",
                        "retrieval_timestamp": retrieval_timestamp,
                        "confidence": _confidence_for_metric(anomaly),
                        "uncertainty_status": "present",
                        "content": {
                            **anomaly,
                            "timestamp": created_at,
                            "service": (
                                execution.input.get("messages", [{}])[-1]
                                if execution.input
                                else None
                            ),
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
                        "retrieval_timestamp": retrieval_timestamp,
                        "confidence": _confidence_for_log(signature),
                        "uncertainty_status": "present",
                        "content": {
                            **signature,
                            "timestamp": signature.get("first_seen") or created_at,
                            "fingerprint": signature.get("fingerprint", ""),
                            "trace_ids": signature.get("trace_ids", []),
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
                        "retrieval_timestamp": retrieval_timestamp,
                        "confidence": _confidence_for_deployment(change),
                        "uncertainty_status": "present" if change.get("commit_sha") else "partial",
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
