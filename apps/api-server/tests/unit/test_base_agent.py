import json

import httpx
import pytest
from agents.base_agent import agent_loop
from core.llm_client import LLMClient
from pydantic import BaseModel
from tools.registry import ToolRegistry


class TimeResponse(BaseModel):
    answer: str


@pytest.mark.asyncio
async def test_agent_loop_uses_tool_then_returns_structured_output() -> None:
    responses = [
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
                                    "name": "get_current_time",
                                    "arguments": "{}",
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
                        "content": json.dumps({"answer": "The time is 10:00 UTC"}),
                    }
                }
            ]
        },
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=responses.pop(0))

    transport = httpx.MockTransport(handler)
    llm_client = LLMClient(base_url="http://test", transport=transport)
    registry = ToolRegistry()

    @registry.tool(
        name="get_current_time",
        description="Return current time",
        parameters={"type": "object", "properties": {}, "required": []},
    )
    async def get_current_time() -> dict[str, str]:
        return {"time": "10:00 UTC"}

    result = await agent_loop(
        llm_client=llm_client,
        system_prompt="Use tools when needed.",
        user_message="Tell me the time",
        tools=["get_current_time"],
        registry=registry,
        output_schema=TimeResponse,
    )

    assert result.answer == "The time is 10:00 UTC"
    await llm_client.close()
