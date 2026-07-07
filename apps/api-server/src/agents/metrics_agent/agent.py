from typing import Any

from agents._base.base_agent import BaseAgent
from agents.base_agent import agent_loop
from agents.metrics_agent.output_schema import MetricsSummary
from agents.metrics_agent.prompts import build_metrics_system_prompt, build_metrics_user_prompt
from core.llm_client import LLMClient
from db.models.incident import Incident
from sqlalchemy.ext.asyncio import AsyncSession
from tools.prometheus.client import PrometheusClient
from tools.prometheus.tools import build_prometheus_registry


class MetricsAgent(BaseAgent):
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        super().__init__("metrics_agent", llm_client)

    async def run(
        self,
        incident: Incident,
        *,
        db_session: AsyncSession | None = None,
        prometheus_client: PrometheusClient | None = None,
    ) -> MetricsSummary:
        registry, owned_prometheus_client = build_prometheus_registry(prometheus_client)
        context: dict[str, Any] = {
            "title": incident.title,
            "summary": incident.summary,
            "service": incident.raw_payload.get("labels", {}).get("service", "unknown"),
            "start": incident.raw_payload.get("starts_at", "now-15m"),
            "end": incident.raw_payload.get("ends_at", "now"),
        }
        result = await agent_loop(
            llm_client=self.llm_client,
            system_prompt=build_metrics_system_prompt(),
            user_message=build_metrics_user_prompt(context),
            tools=["query_prometheus", "get_service_dependencies"],
            registry=registry,
            output_schema=MetricsSummary,
            state=context,
            incident_id=incident.id,
            agent_name=self.name,
            db_session=db_session,
        )
        assert isinstance(result, MetricsSummary)
        if prometheus_client is None:
            await owned_prometheus_client.close()
        return result


async def analyze_metrics(
    incident: Incident,
    *,
    db_session: AsyncSession | None = None,
    llm_client: LLMClient | None = None,
    prometheus_client: PrometheusClient | None = None,
) -> MetricsSummary:
    agent = MetricsAgent(llm_client)
    res = await agent.run(incident, db_session=db_session, prometheus_client=prometheus_client)
    if llm_client is None:
        await agent.llm_client.close()
    return res
