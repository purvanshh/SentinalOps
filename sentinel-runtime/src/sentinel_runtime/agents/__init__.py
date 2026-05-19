"""Runtime agents for incident processing."""

from typing import Any

from sentinel_common.contracts import AgentContract


class BaseAgent:
    """Base class for all runtime agents."""

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def validate_input(self, input_data: dict[str, Any]) -> bool:
        raise NotImplementedError
