"""
Loki log adapter for SentinelOps Phase 47.

Converts Loki query result entries and push API payloads into
normalized raw dicts for TelemetryNormalizer.

Loki query result shape:
  {
    "stream": {"job": "...", "namespace": "...", "pod": "..."},
    "values": [["<nanoseconds_ts>", "<log_line>"], ...]
  }
"""

from __future__ import annotations

from typing import Any


def _nano_to_iso(ns_str: str) -> str:
    """Convert nanosecond Unix timestamp string to ISO-8601."""
    try:
        ns = int(ns_str)
        seconds = ns / 1_000_000_000
        from datetime import datetime, timezone

        dt = datetime.fromtimestamp(seconds, tz=timezone.utc)
        return dt.isoformat()
    except (ValueError, TypeError, OSError):
        return str(ns_str)


def _detect_severity(log_line: str) -> str:
    """Heuristic severity detection from log line content."""
    line_lower = log_line.lower()
    if any(k in line_lower for k in ("fatal", "panic", "critical")):
        return "critical"
    if "error" in line_lower or " err " in line_lower:
        return "error"
    if "warn" in line_lower:
        return "warning"
    if "debug" in line_lower or "trace" in line_lower:
        return "debug"
    return "info"


def adapt_stream_entry(
    stream_labels: dict[str, str],
    ts_ns: str,
    log_line: str,
    incident_id: str | None = None,
) -> dict[str, Any]:
    """Adapt a single Loki stream log entry."""
    service = (
        stream_labels.get("job") or stream_labels.get("app") or stream_labels.get("namespace", "")
    )
    ts_iso = _nano_to_iso(ts_ns)
    severity = stream_labels.get("severity") or _detect_severity(log_line)

    return {
        "event_id": f"loki_{abs(hash(ts_ns + log_line[:50]))}",
        "kind": "log",
        "timestamp_iso": ts_iso,
        "service": service,
        "severity": severity,
        "message": log_line[:500],
        "labels": {str(k): str(v) for k, v in stream_labels.items()},
        "source": "loki",
        "payload": {"log_line": log_line},
        "incident_id": incident_id or stream_labels.get("incident_id"),
    }


def adapt_query_result(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Adapt a Loki query result (stream + values list) into event dicts."""
    stream = result.get("stream", {})
    values = result.get("values", [])
    incident_id = stream.get("incident_id")
    return [adapt_stream_entry(stream, ts, line, incident_id) for ts, line in values]


def adapt_batch(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Adapt a list of Loki query result streams."""
    out: list[dict[str, Any]] = []
    for r in results:
        out.extend(adapt_query_result(r))
    return out
