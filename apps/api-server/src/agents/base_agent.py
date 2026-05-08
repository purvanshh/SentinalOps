import json
from collections.abc import Sequence
from time import perf_counter
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.llm_client import LLMClient
from db.repositories.incident_repo import IncidentRepository
from tools.base import ToolCall
from tools.registry import ToolRegistry


async def agent_loop(
    *,
    llm_client: LLMClient,
    system_prompt: str,
    user_message: str,
    tools: list[str],
    registry: ToolRegistry,
    output_schema: type[BaseModel],
    state: dict[str, Any] | None = None,
    incident_id: UUID | None = None,
    agent_name: str = "generic_agent",
    db_session: AsyncSession | None = None,
    max_iterations: int = 5,
) -> BaseModel:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    if state:
        messages.append({"role": "system", "content": f"Current state: {json.dumps(state, default=str)}"})

    iteration_count = 0
    started_at = perf_counter()

    while iteration_count < max_iterations:
        response = await llm_client.generate(
            messages,
            tools=registry.list_schemas(tools),
        )
        tool_calls = _extract_tool_calls(response)

        if not tool_calls:
            structured_output = output_schema.model_validate_json(_extract_content(response))
            await _record_execution(
                db_session=db_session,
                incident_id=incident_id,
                agent_name=agent_name,
                input_payload={"messages": messages},
                output_payload=structured_output.model_dump(mode="json"),
                status="completed",
                latency=perf_counter() - started_at,
            )
            return structured_output

        messages.append(_assistant_message_from_response(response))
        for tool_call in tool_calls:
            result = await registry.execute(tool_call)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.tool_call_id or tool_call.name,
                    "name": tool_call.name,
                    "content": json.dumps(result.model_dump(mode="json")),
                }
            )
        iteration_count += 1

    raise RuntimeError(f"{agent_name} exceeded max iterations")


def _extract_tool_calls(response: dict[str, Any]) -> list[ToolCall]:
    tool_calls = response.get("tool_calls") or []
    parsed_calls: list[ToolCall] = []
    for call in tool_calls:
        function = call.get("function", {})
        arguments = function.get("arguments", "{}")
        parsed_arguments = json.loads(arguments) if isinstance(arguments, str) else arguments
        parsed_calls.append(
            ToolCall(
                name=function["name"],
                arguments=parsed_arguments,
                tool_call_id=call.get("id"),
            )
        )
    return parsed_calls


def _assistant_message_from_response(response: dict[str, Any]) -> dict[str, Any]:
    message: dict[str, Any] = {
        "role": "assistant",
        "content": response.get("content", ""),
    }
    if response.get("tool_calls"):
        message["tool_calls"] = response["tool_calls"]
    return message


def _extract_content(response: dict[str, Any]) -> str:
    content = response.get("content", "")
    if isinstance(content, list):
        return "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return content


async def _record_execution(
    *,
    db_session: AsyncSession | None,
    incident_id: UUID | None,
    agent_name: str,
    input_payload: dict[str, Any],
    output_payload: dict[str, Any],
    status: str,
    latency: float,
) -> None:
    if db_session is None or incident_id is None:
        return
    repository = IncidentRepository(db_session)
    await repository.create_agent_execution(
        incident_id=incident_id,
        agent_name=agent_name,
        input_payload=input_payload,
        output_payload=output_payload,
        status=status,
        latency=latency,
    )
