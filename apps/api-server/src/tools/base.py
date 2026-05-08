from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    tool_call_id: str | None = None


class ToolResult(BaseModel):
    name: str
    output: dict[str, Any] | list[Any] | str | None = None
    success: bool = True
    error: str | None = None


SafetyLevel = Literal["read_only", "approval_required", "dangerous"]
