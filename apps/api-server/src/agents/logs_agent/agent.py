from typing import Any

from agents.base_agent import agent_loop
from agents.logs_agent.output_schema import LogsSummary
from agents.logs_agent.prompts import build_logs_system_prompt, build_logs_user_prompt
from core.llm_client import LLMClient
from db.models.incident import Incident
from sqlalchemy.ext.asyncio import AsyncSession
from tools.loki.client import LokiClient
from tools.loki.tools import build_loki_registry


async def analyze_logs(
    incident: Incident,
    *,
    db_session: AsyncSession | None = None,
    llm_client: LLMClient | None = None,
    loki_client: LokiClient | None = None,
) -> LogsSummary:
    owned_llm_client = llm_client or LLMClient()
    registry, owned_loki_client = build_loki_registry(loki_client)
    context: dict[str, Any] = {
        "title": incident.title,
        "summary": incident.summary,
        "service": incident.raw_payload.get("labels", {}).get("service", "unknown"),
        "start": incident.raw_payload.get("starts_at", "now-15m"),
        "end": incident.raw_payload.get("ends_at", "now"),
    }
    result = await agent_loop(
        llm_client=owned_llm_client,
        system_prompt=build_logs_system_prompt(),
        user_message=build_logs_user_prompt(context),
        tools=["query_loki", "expand_log_context", "extract_stacktrace"],
        registry=registry,
        output_schema=LogsSummary,
        state=context,
        incident_id=incident.id,
        agent_name="logs_agent",
        db_session=db_session,
    )
    assert isinstance(result, LogsSummary)

    if llm_client is None:
        await owned_llm_client.close()
    if loki_client is None:
        await owned_loki_client.close()
    return result
