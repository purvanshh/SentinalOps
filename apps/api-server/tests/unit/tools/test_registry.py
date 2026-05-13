import pytest
from tools.base import ToolCall
from tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_tool_registry_executes_registered_tool() -> None:
    registry = ToolRegistry()

    @registry.tool(
        name="get_current_time",
        description="Return the current time",
        parameters={"type": "object", "properties": {}, "required": []},
    )
    async def get_current_time() -> dict[str, str]:
        return {"time": "2026-05-08T00:00:00Z"}

    result = await registry.execute(ToolCall(name="get_current_time"))

    assert result.success is True
    assert result.output == {"time": "2026-05-08T00:00:00Z"}
