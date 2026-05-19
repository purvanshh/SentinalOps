"""Failure injection and chaos profiles."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChaosProfile:
    name: str
    failure_type: str
    target_services: list[str] = field(default_factory=list)
    duration: float = 60.0


class FailureInjector:
    """Injects failures into synthetic environments."""

    def inject(self, profile: ChaosProfile) -> dict[str, Any]:
        raise NotImplementedError

    def get_active_failures(self) -> list[ChaosProfile]:
        raise NotImplementedError
