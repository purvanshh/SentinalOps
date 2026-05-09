from __future__ import annotations

from typing import Any

from tools.registry import ToolRegistry
from tools.verification import verify_metric


def build_runtime_registry() -> ToolRegistry:
    registry = ToolRegistry()

    @registry.tool(
        name="rollback_deployment",
        description="Simulate rollback of a deployment for a service.",
        parameters={
            "type": "object",
            "properties": {
                "service": {"type": "string"},
            },
            "required": ["service"],
        },
        safety_level="dangerous",
    )
    async def rollback_deployment(service: str) -> dict[str, Any]:
        return {"service": service, "status": "rolled_back", "mode": "simulated"}

    @registry.tool(
        name="restart_service",
        description="Simulate restarting a service.",
        parameters={
            "type": "object",
            "properties": {
                "service": {"type": "string"},
            },
            "required": ["service"],
        },
        safety_level="dangerous",
    )
    async def restart_service(service: str) -> dict[str, Any]:
        return {"service": service, "status": "restarted", "mode": "simulated"}

    @registry.tool(
        name="scale_service",
        description="Simulate scaling a service.",
        parameters={
            "type": "object",
            "properties": {
                "service": {"type": "string"},
                "replicas": {"type": "integer"},
            },
            "required": ["service", "replicas"],
        },
        safety_level="dangerous",
    )
    async def scale_service(service: str, replicas: int) -> dict[str, Any]:
        return {"service": service, "replicas": replicas, "status": "scaled", "mode": "simulated"}

    @registry.tool(
        name="verify_metric",
        description="Verify that a Prometheus metric is within an expected range.",
        parameters={
            "type": "object",
            "properties": {
                "metric_name": {"type": "string"},
                "expected_min": {"type": "number"},
                "expected_max": {"type": "number"},
            },
            "required": ["metric_name", "expected_min", "expected_max"],
        },
        safety_level="approval_required",
    )
    async def verify_metric_tool(metric_name: str, expected_min: float, expected_max: float) -> dict[str, Any]:
        return await verify_metric(metric_name, expected_min, expected_max)

    return registry
