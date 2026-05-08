from typing import Any

from orchestration.state.topology import get_dependencies, load_topology
from tools.prometheus.client import PrometheusClient
from tools.registry import ToolRegistry


def build_prometheus_registry(
    client: PrometheusClient | None = None,
    *,
    topology: dict[str, Any] | None = None,
) -> tuple[ToolRegistry, PrometheusClient]:
    registry = ToolRegistry()
    prometheus_client = client or PrometheusClient()
    topology_graph = topology or load_topology()

    @registry.tool(
        name="query_prometheus",
        description="Query Prometheus for a metric time range.",
        parameters={
            "type": "object",
            "properties": {
                "promql": {"type": "string"},
                "start": {"type": "string"},
                "end": {"type": "string"},
                "step": {"type": "string"},
            },
            "required": ["promql", "start", "end", "step"],
        },
    )
    async def query_prometheus(promql: str, start: str, end: str, step: str) -> dict[str, Any]:
        return await prometheus_client.query_range(promql, start, end, step)

    @registry.tool(
        name="get_service_dependencies",
        description="Return dependency nodes for a service from the topology graph.",
        parameters={
            "type": "object",
            "properties": {"service": {"type": "string"}},
            "required": ["service"],
        },
    )
    async def service_dependencies(service: str) -> list[dict[str, Any]]:
        return [dependency.model_dump(mode="json") for dependency in get_dependencies(service, topology_graph)]

    return registry, prometheus_client
