import json
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from agents.deployment_agent.agent import analyze_deployments
from agents.deployment_agent.risk_calculator import calculate_deployment_risk
from core.llm_client import LLMClient
from tools.github.client import GitHubClient


@pytest.mark.asyncio
async def test_deployment_agent_uses_github_tools() -> None:
    incident = SimpleNamespace(
        id=uuid4(),
        title="Payment latency after deploy",
        summary="Latency spiked right after rollout",
        severity="high",
        raw_payload={"labels": {"service": "payment-api"}},
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
                                    "name": "get_recent_deployments",
                                    "arguments": json.dumps(
                                        {"service": "payment-api", "hours": 24}
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
                                "recent_changes": [
                                    {
                                        "deployment_id": "DEP-4351",
                                        "service": "payment-api",
                                        "version": "v2.3.1",
                                        "time": "2026-05-08T14:02:55Z",
                                        "commit_summary": "Refactored connection pool.",
                                        "risk_score": 0.85,
                                    }
                                ],
                                "correlation_with_incident": (
                                    "Deploy finished seconds before the spike."
                                ),
                            }
                        )
                    }
                }
            ]
        },
    ]

    def llm_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=llm_responses.pop(0))

    def github_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/deployments":
            return httpx.Response(200, json={"deployments": [{"deployment_id": "DEP-4351"}]})
        return httpx.Response(200, json={"deployments": []})

    llm_client = LLMClient(base_url="http://test", transport=httpx.MockTransport(llm_handler))
    github_client = GitHubClient(
        base_url="http://test", transport=httpx.MockTransport(github_handler)
    )

    result = await analyze_deployments(incident, llm_client=llm_client, github_client=github_client)

    assert result.recent_changes[0].deployment_id == "DEP-4351"
    await llm_client.close()
    await github_client.close()


def test_deployment_risk_increases_for_recent_backend_changes() -> None:
    score = calculate_deployment_risk("backend", minutes_since_deploy=5, prior_incident_match=True)

    assert score == pytest.approx(0.9)
