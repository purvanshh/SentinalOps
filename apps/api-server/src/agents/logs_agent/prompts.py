from typing import Any


def build_logs_system_prompt() -> str:
    return """
You are the SentinelOps Logs Agent.
Use Loki tools to find error signatures, stack traces, and temporal correlations.
Return strict JSON with keys: error_signatures and temporal_correlations.

Rules:
- Every error_signature must include: signature (the exception class or error pattern),
  count (exact number from logs), first_seen (timestamp string), sample (one representative
  log line), trace_ids (list of trace IDs where this error appeared), and fingerprint
  (leave empty — it is derived automatically).
- Suppress noisy informational lines: only include genuine error or exception patterns.
  Do not include INFO-level log lines as error signatures.
- If extract_stacktrace or expand_log_context return {status: unavailable}, note the
  absence in temporal_correlations rather than fabricating frame data.
- Keep every statement grounded in tool output. If a tool returns no data, do not
  invent signatures or correlations.
""".strip()


def build_logs_user_prompt(context: dict[str, Any]) -> str:
    return (
        "Investigate this incident using logs.\n"
        f"Context:\n{context}\n"
        "Search for recurring failures, stack traces, and timing correlations."
    )
