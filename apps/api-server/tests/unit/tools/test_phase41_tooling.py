"""
Phase 41 validation tests: Real Tooling & Evidence Grounding.

Proves:
  A. expand_log_context queries Loki by trace_id and returns real entries or
     structured unavailability — never fabricated placeholder text.
  B. extract_stacktrace parses frame lines from log text and returns structured
     unavailability when no stack trace pattern is found.
  C. rollback_deployment, restart_service, scale_service return
     execution_requested with requires_infrastructure_execution=True,
     never claiming the action completed ("mode": "simulated").
  D. PagerDuty and Confluence integrations return synced/exported=False with
     an unavailable_reason field, not a "stub recorded" message.
"""

from __future__ import annotations

import json

import httpx
import pytest
from tools.loki.client import LokiClient
from tools.loki.tools import build_loki_registry
from tools.runtime_tools import build_runtime_registry

# ─── A. expand_log_context ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_expand_log_context_returns_loki_entries_when_found() -> None:
    loki_payload = {
        "status": "success",
        "data": {
            "result": [
                {
                    "stream": {"trace_id": "abc123", "service": "payment-api"},
                    "values": [["1700000001000000000", "payment flow started"]],
                }
            ]
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=loki_payload)

    loki_client = LokiClient(base_url="http://test", transport=httpx.MockTransport(handler))
    registry, _ = build_loki_registry(loki_client)
    tool = registry.get("expand_log_context")

    result = await tool.handler(trace_id="abc123")

    assert result["status"] == "present"
    assert result["trace_id"] == "abc123"
    assert result["entry_count"] == 1
    assert result["context"][0]["line"] == "payment flow started"
    await loki_client.close()


@pytest.mark.asyncio
async def test_expand_log_context_returns_unavailability_when_no_entries() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "success", "data": {"result": []}})

    loki_client = LokiClient(base_url="http://test", transport=httpx.MockTransport(handler))
    registry, _ = build_loki_registry(loki_client)
    tool = registry.get("expand_log_context")

    result = await tool.handler(trace_id="missing-trace")

    assert result["status"] == "unavailable"
    assert "no log entries found" in result["reason"]
    assert result["trace_id"] == "missing-trace"
    await loki_client.close()


@pytest.mark.asyncio
async def test_expand_log_context_never_returns_fabricated_context_string() -> None:
    """The old implementation returned `[f"context for {trace_id}"]` — must not exist."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "success", "data": {"result": []}})

    loki_client = LokiClient(base_url="http://test", transport=httpx.MockTransport(handler))
    registry, _ = build_loki_registry(loki_client)
    tool = registry.get("expand_log_context")

    result = await tool.handler(trace_id="xyz789")

    result_str = json.dumps(result)
    assert (
        "context for xyz789" not in result_str
    ), "expand_log_context returned fabricated context string — old placeholder behavior detected"
    await loki_client.close()


@pytest.mark.asyncio
async def test_expand_log_context_returns_unavailability_on_loki_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server error")

    loki_client = LokiClient(base_url="http://test", transport=httpx.MockTransport(handler))
    registry, _ = build_loki_registry(loki_client)
    tool = registry.get("expand_log_context")

    result = await tool.handler(trace_id="fail-trace")

    assert result["status"] == "unavailable"
    assert "loki query failed" in result["reason"]
    await loki_client.close()


# ─── B. extract_stacktrace ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_extract_stacktrace_parses_python_traceback() -> None:
    log_entry = (
        "2024-01-01 14:00:00 ERROR payment-api\n"
        "Traceback (most recent call last):\n"
        '  File "payment/service.py", line 42, in process\n'
        "    result = db.execute(query)\n"
        "sqlalchemy.exc.OperationalError: connection refused\n"
    )

    loki_client = LokiClient(
        base_url="http://test",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})),
    )
    registry, _ = build_loki_registry(loki_client)
    tool = registry.get("extract_stacktrace")

    result = await tool.handler(log_entry=log_entry)

    assert result["status"] == "present"
    assert "sqlalchemy.exc.OperationalError" in result["stacktrace"]
    assert result["frame_count"] >= 1
    await loki_client.close()


@pytest.mark.asyncio
async def test_extract_stacktrace_returns_unavailability_for_clean_log() -> None:
    log_entry = "2024-01-01 14:00:00 INFO payment-api - request completed in 50ms"

    loki_client = LokiClient(
        base_url="http://test",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})),
    )
    registry, _ = build_loki_registry(loki_client)
    tool = registry.get("extract_stacktrace")

    result = await tool.handler(log_entry=log_entry)

    assert result["status"] == "unavailable"
    assert "no stack trace pattern detected" in result["reason"]
    await loki_client.close()


@pytest.mark.asyncio
async def test_extract_stacktrace_does_not_return_arbitrary_noise_lines() -> None:
    """Old implementation returned the entire log_entry string verbatim.

    Verify that non-exception/non-frame lines appended BEFORE the exception are
    not included in the extracted stacktrace (i.e., we extract, not pass-through).
    """
    noise_header = "\n".join(f"INFO payment-api: metric tick {i}" for i in range(50))
    exception_block = (
        "TimeoutException: payment gateway timed out after 30s\n"
        '  File "payment/service.py", line 42, in process\n'
    )
    log_entry_with_noise = noise_header + "\n" + exception_block

    loki_client = LokiClient(
        base_url="http://test",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})),
    )
    registry, _ = build_loki_registry(loki_client)
    tool = registry.get("extract_stacktrace")

    result = await tool.handler(log_entry=log_entry_with_noise)

    assert result.get("status") == "present"
    assert len(result["stacktrace"]) < len(
        log_entry_with_noise
    ), "extract_stacktrace returned the entire raw log entry — old pass-through behavior detected"
    assert (
        "metric tick 0" not in result["stacktrace"]
    ), "Non-exception noise lines leaked into the extracted stacktrace"
    await loki_client.close()


# ─── C. runtime tools honest execution status ─────────────────────────────────


@pytest.mark.asyncio
async def test_rollback_deployment_returns_execution_requested() -> None:
    registry = build_runtime_registry()
    tool = registry.get("rollback_deployment")

    result = await tool.handler(service="payment-api")

    assert result["status"] == "execution_requested"
    assert result["requires_infrastructure_execution"] is True
    assert result["service"] == "payment-api"


@pytest.mark.asyncio
async def test_rollback_deployment_does_not_claim_completion() -> None:
    registry = build_runtime_registry()
    tool = registry.get("rollback_deployment")

    result = await tool.handler(service="payment-api")

    result_str = json.dumps(result)
    assert "simulated" not in result_str, "rollback_deployment still returns 'mode: simulated'"
    assert "rolled_back" not in result_str, "rollback_deployment falsely claims rollback completed"


@pytest.mark.asyncio
async def test_restart_service_returns_execution_requested() -> None:
    registry = build_runtime_registry()
    tool = registry.get("restart_service")

    result = await tool.handler(service="order-service")

    assert result["status"] == "execution_requested"
    assert result["requires_infrastructure_execution"] is True
    assert "simulated" not in json.dumps(result)


@pytest.mark.asyncio
async def test_scale_service_returns_execution_requested() -> None:
    registry = build_runtime_registry()
    tool = registry.get("scale_service")

    result = await tool.handler(service="api-gateway", replicas=5)

    assert result["status"] == "execution_requested"
    assert result["replicas"] == 5
    assert result["requires_infrastructure_execution"] is True
    assert "simulated" not in json.dumps(result)


# ─── D. PagerDuty / Confluence honest unavailability ──────────────────────────


@pytest.mark.asyncio
async def test_pagerduty_sync_returns_unavailable_reason() -> None:
    from tools.pagerduty.client import sync_incident_status

    result = await sync_incident_status("inc-001", severity="critical", status="acknowledged")

    assert result["synced"] is False
    assert "unavailable_reason" in result
    assert (
        "stub" not in result["unavailable_reason"].lower()
    ), "pagerduty client still uses 'stub' language — should indicate integration is not configured"


@pytest.mark.asyncio
async def test_confluence_export_returns_unavailable_reason() -> None:
    from tools.confluence.client import export_postmortem

    result = await export_postmortem(
        incident_id="inc-001",
        title="Payment API Latency Spike",
        content="Postmortem content here.",
    )

    assert result["exported"] is False
    assert "unavailable_reason" in result
    assert "stub" not in result["unavailable_reason"].lower(), (
        "confluence client still uses 'stub' language and should indicate "
        "the integration is not configured"
    )
