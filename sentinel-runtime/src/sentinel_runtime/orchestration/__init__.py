"""LangGraph-based orchestration for incident pipeline."""

from typing import Any


class GraphOrchestrator:
    """Orchestrates the incident processing graph."""

    async def run(self, incident: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    async def resume(self, thread_id: str, approval: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
