import json

import httpx
import pytest
from pydantic import BaseModel

from core.llm_client import LLMClient


class GreetingResponse(BaseModel):
    greeting: str


@pytest.mark.asyncio
async def test_llm_client_parses_structured_output() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps({"greeting": "hello"}),
                        }
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    client = LLMClient(base_url="http://test", transport=transport)

    response = await client.generate(
        [{"role": "user", "content": "say hi"}],
        structured_output_model=GreetingResponse,
    )

    assert isinstance(response, GreetingResponse)
    assert response.greeting == "hello"
    await client.close()
