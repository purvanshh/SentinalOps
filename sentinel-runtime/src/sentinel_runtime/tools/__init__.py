"""Tool integrations for runtime agents."""

from typing import Any


class ToolRegistry:
    """Registry of available tools for agents."""

    def register(self, name: str, tool: Any) -> None:
        raise NotImplementedError

    def get(self, name: str) -> Any:
        raise NotImplementedError
