"""
Kubernetes event adapter for SentinelOps Phase 47.

Converts Kubernetes Event objects and pod phase changes into
normalized raw dicts for TelemetryNormalizer.

K8s Event object shape:
  {
    "type": "Warning",
    "reason": "OOMKilling",
    "message": "...",
    "involvedObject": {"kind": "Pod", "name": "...", "namespace": "..."},
    "firstTimestamp": "...",
    "lastTimestamp": "...",
    "count": 3,
    "metadata": {"name": "...", "namespace": "..."}
  }
"""

from __future__ import annotations

from typing import Any

_K8S_TYPE_TO_SEVERITY: dict[str, str] = {
    "Warning": "warning",
    "Normal": "info",
    "Error": "error",
}

_K8S_REASON_TO_SEVERITY: dict[str, str] = {
    "OOMKilling": "critical",
    "BackOff": "error",
    "Failed": "error",
    "FailedScheduling": "error",
    "FailedMount": "error",
    "CrashLoopBackOff": "critical",
    "Evicted": "error",
    "Killing": "warning",
    "Pulled": "info",
    "Created": "info",
    "Started": "info",
    "Scheduled": "info",
}


def adapt_event(raw: dict[str, Any]) -> dict[str, Any]:
    """Adapt a Kubernetes Event object."""
    involved = raw.get("involvedObject", {})
    metadata = raw.get("metadata", {})
    namespace = involved.get("namespace") or metadata.get("namespace", "")
    obj_name = involved.get("name", "")
    obj_kind = involved.get("kind", "")
    reason = raw.get("reason", "")
    message = raw.get("message", "")
    k8s_type = raw.get("type", "Normal")
    ts = raw.get("lastTimestamp") or raw.get("firstTimestamp", "")

    # Service = namespace/resource-name (normalized later)
    service = namespace or obj_name

    severity = _K8S_REASON_TO_SEVERITY.get(reason, _K8S_TYPE_TO_SEVERITY.get(k8s_type, "info"))

    labels = {
        "namespace": str(namespace),
        "object_kind": str(obj_kind),
        "object_name": str(obj_name),
        "reason": str(reason),
        "k8s_type": str(k8s_type),
        "count": str(raw.get("count", 1)),
    }

    return {
        "event_id": f"k8s_{metadata.get('name', abs(hash(ts + reason + obj_name)))}",
        "kind": "alert" if k8s_type == "Warning" else "log",
        "timestamp_iso": ts,
        "service": service,
        "severity": severity,
        "message": f"{reason}: {message}",
        "labels": labels,
        "source": "kubernetes",
        "payload": raw,
        "incident_id": metadata.get("labels", {}).get("incident_id"),
    }


def adapt_pod_phase(raw: dict[str, Any]) -> dict[str, Any]:
    """Adapt a Kubernetes pod phase change record."""
    metadata = raw.get("metadata", {})
    status = raw.get("status", {})
    phase = status.get("phase", "Unknown")
    namespace = metadata.get("namespace", "")
    name = metadata.get("name", "")
    ts = status.get("startTime") or metadata.get("creationTimestamp", "")

    phase_severity = {
        "Failed": "error",
        "Unknown": "warning",
        "Pending": "info",
        "Running": "info",
        "Succeeded": "info",
    }

    labels = metadata.get("labels", {})
    service = labels.get("app") or labels.get("app.kubernetes.io/name") or namespace

    return {
        "event_id": f"k8s_pod_{namespace}_{name}_{phase}",
        "kind": "log",
        "timestamp_iso": ts,
        "service": service,
        "severity": phase_severity.get(phase, "info"),
        "message": f"Pod {name} in phase {phase}",
        "labels": {str(k): str(v) for k, v in labels.items()},
        "source": "kubernetes",
        "payload": raw,
        "incident_id": labels.get("incident_id"),
    }


def adapt_batch(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Adapt a list of Kubernetes event objects."""
    return [adapt_event(ev) for ev in events]
