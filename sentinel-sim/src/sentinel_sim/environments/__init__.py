"""Synthetic environments and service topologies."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ServiceTopology:
    services: list[str] = field(default_factory=list)
    edges: list[tuple[str, str]] = field(default_factory=list)

    def get_dependencies(self, service: str) -> list[str]:
        raise NotImplementedError


class SyntheticEnvironment:
    """Manages a synthetic environment for simulation."""

    def setup(self, topology: ServiceTopology) -> None:
        raise NotImplementedError

    def teardown(self) -> None:
        raise NotImplementedError

    def get_state(self) -> dict[str, Any]:
        raise NotImplementedError
