"""Telemetry data models."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class TelemetryEvent:
    event_type: str
    timestamp: datetime
    source: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricPoint:
    name: str
    value: float
    timestamp: datetime
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class LogEntry:
    level: str
    message: str
    timestamp: datetime
    service: str
    trace_id: str | None = None


@dataclass
class TraceSpan:
    trace_id: str
    span_id: str
    parent_id: str | None
    operation: str
    start_time: datetime
    duration_ms: float
