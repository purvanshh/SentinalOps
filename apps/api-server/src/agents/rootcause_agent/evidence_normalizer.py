from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from db.models.agent_execution import AgentExecution


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _confidence_for_metric(anomaly: dict[str, Any]) -> float:
    """Derive a confidence score from the anomaly's deviation magnitude."""
    deviation = anomaly.get("deviation_factor", anomaly.get("deviation"))
    if deviation is not None:
        try:
            magnitude = float(deviation)
        except (TypeError, ValueError):
            magnitude = None
        if magnitude is not None:
            return round(min(0.95, max(0.5, magnitude / 2.0)), 2)

    z_score = anomaly.get("z_score")
    if z_score is not None:
        try:
            magnitude = float(z_score)
        except (TypeError, ValueError):
            magnitude = None
        if magnitude is not None:
            return round(min(0.95, max(0.5, magnitude / 10.0)), 2)

    return 0.5


def _infer_service_name(evidence_item: dict[str, Any], execution: AgentExecution) -> str | None:
    service = evidence_item.get("service")
    if service:
        return str(service)

    execution_input = execution.input or {}
    service = execution_input.get("service")
    if service:
        return str(service)

    raw_payload = execution_input.get("raw_payload", {})
    if isinstance(raw_payload, dict):
        service = raw_payload.get("labels", {}).get("service")
        if service:
            return str(service)

    joined_text = " ".join(
        str(value)
        for key, value in evidence_item.items()
        if key in {"metric", "signature", "sample", "summary"}
    ).lower()
    service_markers = {
        "payment": "payment-api",
        "search": "search-service",
        "auth": "auth-service",
        "gateway": "api-gateway",
        "notification": "notification-service",
        "order": "order-service",
        "checkout": "checkout-service",
        "user": "user-service",
    }
    for marker, inferred_service in service_markers.items():
        if marker in joined_text:
            return inferred_service
    return None


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
                            "service": _infer_service_name(anomaly, execution),
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
                            "service": _infer_service_name(signature, execution),
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
