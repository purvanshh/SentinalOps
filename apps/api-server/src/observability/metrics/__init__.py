from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

API_REQUEST_COUNT = Counter("api_requests_total", "Total API requests handled by SentinelOps")
INCIDENT_COUNT = Counter("incidents_total", "Total incidents created")
AGENT_EXECUTION_COUNT = Counter("agent_executions_total", "Total agent executions")
TOOL_FAILURE_COUNT = Counter("tool_failures_total", "Total failed tool calls")
AGENT_DURATION_SECONDS = Histogram("agent_duration_seconds", "Agent execution duration in seconds")
APPROVAL_WAIT_SECONDS = Histogram("approval_wait_seconds", "Approval wait time in seconds")


def build_metrics_snapshot() -> dict[str, float]:
    return {
        "api_requests_total": float(API_REQUEST_COUNT._value.get()),  # noqa: SLF001
        "incidents_total": float(INCIDENT_COUNT._value.get()),  # noqa: SLF001
        "agent_executions_total": float(AGENT_EXECUTION_COUNT._value.get()),  # noqa: SLF001
        "tool_failures_total": float(TOOL_FAILURE_COUNT._value.get())  # noqa: SLF001
    }


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
