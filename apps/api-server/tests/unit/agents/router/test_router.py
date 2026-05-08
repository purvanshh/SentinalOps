import json
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from agents.router_agent.agent import classify_incident
from core.llm_client import LLMClient
from retrieval.incident_history.searcher import IncidentHistorySearcher


@pytest.mark.asyncio
async def test_router_agent_classifies_incident() -> None:
    incident = SimpleNamespace(
        id=uuid4(),
        title="Payment API latency high",
        summary="p99 latency exceeded threshold",
        severity="high",
        source="prometheus",
        raw_payload={"labels": {"service": "payment-api"}, "annotations": {}},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    def llm_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "incident_type": "database_latency",
                                    "severity": "high",
                                    "confidence": 0.91,
                                    "requires_immediate_investigation": True,
                                    "recommended_workflow": "full_investigation",
                                    "rationale": "Latency pattern matches database contention.",
                                }
                            )
                        }
                    }
                ]
            },
        )

    llm_client = LLMClient(base_url="http://test", transport=httpx.MockTransport(llm_handler))
    searcher = IncidentHistorySearcher(
        base_url="http://test",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={"result": [{"score": 0.9, "payload": {"incident_id": "INC-1"}}]},
            )
        ),
    )

    result = await classify_incident(incident, llm_client=llm_client, searcher=searcher)

    assert result.incident_type == "database_latency"
    assert result.confidence == pytest.approx(0.91)
    await llm_client.close()
    await searcher.close()
