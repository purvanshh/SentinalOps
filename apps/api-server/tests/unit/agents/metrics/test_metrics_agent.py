import json
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from agents.metrics_agent.agent import analyze_metrics
from core.llm_client import LLMClient
from tools.prometheus.client import PrometheusClient


@pytest.mark.asyncio
async def test_metrics_agent_uses_prometheus_tools() -> None:
    incident = SimpleNamespace(
        id=uuid4(),
        title="CPU spike on payment-api",
        summary="Latency and CPU rose sharply",
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
                                    "name": "query_prometheus",
                                    "arguments": json.dumps(
                                        {
                                            "promql": "cpu_usage",
                                            "start": "1",
                                            "end": "2",
                                            "step": "60s",
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
                                "summary": "CPU spiked to 98%.",
                                "anomalies": [
                                    {
                                        "metric": "cpu_usage",
                                        "observed": "98%",
                                        "expected_range": "30-50%",
                                        "z_score": 5.2,
                                    }
                                ],
                                "correlation_hints": ["Spike aligned with request surge."],
                                "raw_query_links": ["http://prometheus/query"],
                            }
                        )
                    }
                }
            ]
        },
    ]

    def llm_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=llm_responses.pop(0))

    def prom_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "success", "data": {"result": []}})

    llm_client = LLMClient(base_url="http://test", transport=httpx.MockTransport(llm_handler))
    prom_client = PrometheusClient(
        base_url="http://test", transport=httpx.MockTransport(prom_handler)
    )

    result = await analyze_metrics(incident, llm_client=llm_client, prometheus_client=prom_client)

    assert result.anomalies[0].metric == "cpu_usage"
    await llm_client.close()
    await prom_client.close()
