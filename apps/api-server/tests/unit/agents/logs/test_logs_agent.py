import json
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from agents.logs_agent.agent import analyze_logs
from core.llm_client import LLMClient
from tools.loki.client import LokiClient


@pytest.mark.asyncio
async def test_logs_agent_uses_loki_tools() -> None:
    incident = SimpleNamespace(
        id=uuid4(),
        title="Error spike on payment-api",
        summary="Timeout exceptions increased",
        raw_payload={"labels": {"service": "payment-api"}, "starts_at": "1", "ends_at": "2"},
    )

    llm_responses = [
        {
            "choices": [
                {
                    "message": {
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call-1",
                                "type": "function",
                                "function": {
                                    "name": "query_loki",
                                    "arguments": json.dumps(
                                        {
                                            "logql": '{service="payment-api"}',
                                            "start": "1",
                                            "end": "2",
                                        }
                                    ),
                                },
                            }
                        ],
                    }
                }
            ]
        },
        {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "error_signatures": [
                                    {
                                        "signature": "TimeoutException",
                                        "count": 42,
                                        "first_seen": "14:03:01",
                                        "sample": "TimeoutException in payment flow",
                                        "trace_ids": ["abc123"],
                                    }
                                ],
                                "temporal_correlations": [
                                    {
                                        "event": "deploy completed",
                                        "timestamp": "14:02:55",
                                        "relation": "6 seconds before first error",
                                    }
                                ],
                            }
                        )
                    }
                }
            ]
        },
    ]

    def llm_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=llm_responses.pop(0))

    def loki_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "success", "data": {"result": []}})

    llm_client = LLMClient(base_url="http://test", transport=httpx.MockTransport(llm_handler))
    loki_client = LokiClient(base_url="http://test", transport=httpx.MockTransport(loki_handler))

    result = await analyze_logs(incident, llm_client=llm_client, loki_client=loki_client)

    assert result.error_signatures[0].signature == "TimeoutException"
    await llm_client.close()
    await loki_client.close()
