"""Incident and scenario generators."""

from typing import Any

from sentinel_common.schemas import IncidentSchema


class IncidentGenerator:
    """Generates synthetic incidents for testing."""

    def generate(self, category: str, count: int = 1) -> list[IncidentSchema]:
        raise NotImplementedError


class ScenarioBuilder:
    """Builds multi-step incident scenarios."""

    def build(self, config: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
