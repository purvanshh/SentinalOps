from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel, ValidationError

from tools.base import SafetyLevel, ToolCall, ToolResult

ToolHandler = Callable[..., Awaitable[Any]]


class RegisteredTool(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any]
    safety_level: SafetyLevel
    handler: ToolHandler

    model_config = {"arbitrary_types_allowed": True}

    def openai_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def tool(
        self,
        *,
        name: str,
        description: str,
        parameters: dict[str, Any],
        safety_level: SafetyLevel = "read_only",
    ) -> Callable[[ToolHandler], ToolHandler]:
        def decorator(func: ToolHandler) -> ToolHandler:
            self._tools[name] = RegisteredTool(
                name=name,
                description=description,
                parameters=parameters,
                safety_level=safety_level,
                handler=func,
            )
            return func

        return decorator

    def get(self, name: str) -> RegisteredTool:
        return self._tools[name]

    def list_schemas(self, tool_names: list[str] | None = None) -> list[dict[str, Any]]:
        selected = self._tools.values() if tool_names is None else (
            self._tools[name] for name in tool_names if name in self._tools
        )
        return [tool.openai_schema() for tool in selected]

    async def execute(self, tool_call: ToolCall) -> ToolResult:
        tool = self.get(tool_call.name)
        try:
            output = await tool.handler(**tool_call.arguments)
            return ToolResult(name=tool_call.name, output=output, success=True)
        except ValidationError as exc:
            return ToolResult(name=tool_call.name, success=False, error=str(exc))
        except Exception as exc:  # noqa: BLE001
            return ToolResult(name=tool_call.name, success=False, error=str(exc))
