from time import perf_counter
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from agents.base_agent import agent_loop
from agents.metrics_agent.output_schema import MetricsSummary
from agents.metrics_agent.prompts import build_metrics_system_prompt, build_metrics_user_prompt
from core.llm_client import LLMClient
from db.models.incident import Incident
from tools.prometheus.client import PrometheusClient
from tools.prometheus.tools import build_prometheus_registry


async def analyze_metrics(
    incident: Incident,
    *,
    db_session: AsyncSession | None = None,
    llm_client: LLMClient | None = None,
    prometheus_client: PrometheusClient | None = None,
) -> MetricsSummary:
    owned_llm_client = llm_client or LLMClient()
    registry, owned_prometheus_client = build_prometheus_registry(prometheus_client)
    started_at = perf_counter()
    context: dict[str, Any] = {
        "title": incident.title,
        "summary": incident.summary,
        "service": incident.raw_payload.get("labels", {}).get("service", "unknown"),
        "start": incident.raw_payload.get("starts_at", "now-15m"),
        "end": incident.raw_payload.get("ends_at", "now"),
    }
    result = await agent_loop(
        llm_client=owned_llm_client,
        system_prompt=build_metrics_system_prompt(),
        user_message=build_metrics_user_prompt(context),
        tools=["query_prometheus", "get_service_dependencies"],
        registry=registry,
        output_schema=MetricsSummary,
        state=context,
        incident_id=incident.id,
        agent_name="metrics_agent",
        db_session=db_session,
    )
    assert isinstance(result, MetricsSummary)

    if llm_client is None:
        await owned_llm_client.close()
    if prometheus_client is None:
        await owned_prometheus_client.close()
    _ = started_at
    return result
