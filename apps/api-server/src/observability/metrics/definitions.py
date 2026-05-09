from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

API_REQUESTS_TOTAL = Counter(
    "api_requests_total",
    "Total API requests handled by SentinelOps",
    labelnames=("method", "route"),
)
INCIDENTS_TOTAL = Counter(
    "incidents_total",
    "Total incidents created",
    labelnames=("source",),
)
AGENT_EXECUTIONS_TOTAL = Counter(
    "agent_executions_total",
    "Total agent executions",
    labelnames=("agent", "status"),
)
TOOL_EXECUTIONS_TOTAL = Counter(
    "tool_executions_total",
    "Total tool executions",
    labelnames=("tool", "outcome"),
)
AGENT_DURATION_SECONDS = Histogram(
    "agent_duration_seconds",
    "Agent execution duration in seconds",
    labelnames=("agent",),
)
APPROVAL_WAIT_SECONDS = Histogram(
    "approval_wait_seconds",
    "Approval wait time in seconds",
    labelnames=("status",),
)

_METRIC_SNAPSHOT = {
    "api_requests_total": 0.0,
    "incidents_total": 0.0,
    "agent_executions_total": 0.0,
    "tool_executions_total": 0.0,
}


def observe_api_request(method: str, route: str) -> None:
    API_REQUESTS_TOTAL.labels(method=method, route=route).inc()
    _METRIC_SNAPSHOT["api_requests_total"] += 1


def observe_incident_created(source: str) -> None:
    INCIDENTS_TOTAL.labels(source=source).inc()
    _METRIC_SNAPSHOT["incidents_total"] += 1


def observe_agent_execution(agent: str, status: str, latency: float | None = None) -> None:
    AGENT_EXECUTIONS_TOTAL.labels(agent=agent, status=status).inc()
    _METRIC_SNAPSHOT["agent_executions_total"] += 1
    if latency is not None:
        AGENT_DURATION_SECONDS.labels(agent=agent).observe(latency)


def observe_tool_execution(tool: str, outcome: str) -> None:
    TOOL_EXECUTIONS_TOTAL.labels(tool=tool, outcome=outcome).inc()
    _METRIC_SNAPSHOT["tool_executions_total"] += 1


def observe_approval_wait(seconds: float, status: str) -> None:
    APPROVAL_WAIT_SECONDS.labels(status=status).observe(seconds)


def build_metrics_snapshot() -> dict[str, float]:
    return dict(_METRIC_SNAPSHOT)


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
