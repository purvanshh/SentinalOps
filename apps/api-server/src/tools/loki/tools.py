from typing import Any

from tools.loki.client import LokiClient
from tools.registry import ToolRegistry

_TRACE_EXCEPTION_MARKERS = (
    "Exception",
    "Error:",
    "Traceback",
    "Caused by:",
    "Panic:",
    "panic:",
    "FATAL",
    "EXCEPTION",
)

_FRAME_PREFIXES = (
    "\tat ",  # Java: at com.example.Foo.bar(Foo.java:42)
    '  File "',  # Python: File "path/to/file.py", line N
    '\tFile "',  # Python with tab indent
    "    at ",  # Node.js / V8
    "  at ",  # some JS runtimes
    "\tat\t",  # Go-style goroutine frames
)


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
        description=(
            "Retrieve log lines associated with a trace identifier from Loki. "
            "Returns actual log entries or explicit unavailability when no entries exist."
        ),
        parameters={
            "type": "object",
            "properties": {"trace_id": {"type": "string"}},
            "required": ["trace_id"],
        },
    )
    async def expand_log_context(trace_id: str) -> dict[str, Any]:
        try:
            result = await loki_client.query_range(
                f'{{trace_id="{trace_id}"}}',
                "now-30m",
                "now",
            )
            entries: list[dict[str, Any]] = []
            for stream in result.get("data", {}).get("result", []):
                labels = stream.get("stream", {})
                for ts, line in stream.get("values", []):
                    entries.append({"timestamp": ts, "line": line, "labels": labels})
            if not entries:
                return {
                    "status": "unavailable",
                    "reason": "no log entries found for trace_id in the 30-minute search window",
                    "trace_id": trace_id,
                }
            return {
                "status": "present",
                "trace_id": trace_id,
                "entry_count": len(entries),
                "context": entries[:50],
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "status": "unavailable",
                "reason": f"loki query failed: {exc}",
                "trace_id": trace_id,
            }

    @registry.tool(
        name="extract_stacktrace",
        description=(
            "Extract stack frame lines from a raw log entry string. "
            "Returns structured frame data or explicit unavailability "
            "when no trace pattern is found."
        ),
        parameters={
            "type": "object",
            "properties": {"log_entry": {"type": "string"}},
            "required": ["log_entry"],
        },
    )
    async def extract_stacktrace(log_entry: str) -> dict[str, Any]:
        lines = log_entry.splitlines()
        frame_lines: list[str] = []
        in_trace = False

        for line in lines:
            if any(marker in line for marker in _TRACE_EXCEPTION_MARKERS):
                in_trace = True
            if in_trace:
                frame_lines.append(line)

        if not frame_lines:
            return {
                "status": "unavailable",
                "reason": "no stack trace pattern detected in log entry",
            }

        meaningful = [
            ln
            for ln in frame_lines
            if any(ln.startswith(p) for p in _FRAME_PREFIXES)
            or any(marker in ln for marker in _TRACE_EXCEPTION_MARKERS)
        ]
        frames = (meaningful or frame_lines)[:20]

        return {
            "status": "present",
            "stacktrace": "\n".join(frames),
            "frame_count": len(frames),
        }

    return registry, loki_client
