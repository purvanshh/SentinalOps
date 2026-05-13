"""
Prometheus telemetry adapter for SentinelOps Phase 47.

Converts Prometheus alert manager webhook payloads and metric query
results into normalized raw dicts for TelemetryNormalizer.

Prometheus alert payload shape:
  {
    "status": "firing",
    "labels": {"alertname": "...", "severity": "...", "job": "..."},
    "annotations": {"summary": "...", "description": "..."},
    "startsAt": "2026-05-01T10:00:00Z",
    "endsAt": "0001-01-01T00:00:00Z",
    "generatorURL": "..."
  }
"""

from __future__ import annotations

from typing import Any


def adapt_alert(raw: dict[str, Any]) -> dict[str, Any]:
    """Adapt a Prometheus alert manager webhook payload."""
    labels = raw.get("labels", {})
    annotations = raw.get("annotations", {})
    status = raw.get("status", "")

    severity_raw = labels.get("severity", status or "warning")
    service = labels.get("job") or labels.get("service") or labels.get("namespace", "")
    description = (
        annotations.get("description") or annotations.get("summary") or labels.get("alertname", "")
    )
    ts = raw.get("startsAt") or raw.get("timestamp_iso", "")

    return {
        "event_id": labels.get("alertname", "") + "_" + ts[:19].replace(":", "").replace("-", ""),
        "kind": "alert",
        "timestamp_iso": ts,
        "service": service,
        "severity": severity_raw,
        "message": description,
        "labels": {str(k): str(v) for k, v in labels.items()},
        "source": "prometheus",
        "payload": {"raw_labels": labels, "annotations": annotations},
        "incident_id": labels.get("incident_id"),
    }


def adapt_metric(raw: dict[str, Any]) -> dict[str, Any]:
    """Adapt a Prometheus instant query result row."""
    metric = raw.get("metric", {})
    value = raw.get("value", [None, None])
    ts = value[0] if value else None
    val = value[1] if len(value) > 1 else None

    service = metric.get("job") or metric.get("service", "")
    return {
        "event_id": f"prom_{metric.get('__name__', 'metric')}_{service}",
        "kind": "metric",
        "timestamp_iso": ts,
        "service": service,
        "severity": "info",
        "message": f"{metric.get('__name__', 'metric')}={val}",
        "labels": {str(k): str(v) for k, v in metric.items()},
        "source": "prometheus",
        "payload": {"metric": metric, "value": val},
        "incident_id": metric.get("incident_id"),
    }


def adapt_batch(raw_alerts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Adapt a list of Prometheus alert payloads."""
    return [adapt_alert(a) for a in raw_alerts]
