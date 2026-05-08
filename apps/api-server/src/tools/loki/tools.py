from typing import Any

from tools.loki.client import LokiClient
from tools.registry import ToolRegistry


def build_loki_registry(client: LokiClient | None = None) -> tuple[ToolRegistry, LokiClient]:
    registry = ToolRegistry()
    loki_client = client or LokiClient()

    @registry.tool(
        name="query_loki",
        description="Query Loki logs within a time range.",
        parameters={
            "type": "object",
            "properties": {
                "logql": {"type": "string"},
                "start": {"type": "string"},
                "end": {"type": "string"},
            },
            "required": ["logql", "start", "end"],
        },
    )
    async def query_loki(logql: str, start: str, end: str) -> dict[str, Any]:
        return await loki_client.query_range(logql, start, end)

    @registry.tool(
        name="expand_log_context",
        description="Return expanded log context for a trace identifier.",
        parameters={
            "type": "object",
            "properties": {"trace_id": {"type": "string"}},
            "required": ["trace_id"],
        },
    )
    async def expand_log_context(trace_id: str) -> dict[str, Any]:
        return {"trace_id": trace_id, "context": [f"context for {trace_id}"]}

    @registry.tool(
        name="extract_stacktrace",
        description="Extract a stack trace string from a log entry.",
        parameters={
            "type": "object",
            "properties": {"log_entry": {"type": "string"}},
            "required": ["log_entry"],
        },
    )
    async def extract_stacktrace(log_entry: str) -> dict[str, Any]:
        if "Exception" in log_entry or "Traceback" in log_entry:
            return {"stacktrace": log_entry}
        return {"stacktrace": ""}

    return registry, loki_client
