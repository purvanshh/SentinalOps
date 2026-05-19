"""Traffic simulation and load profiles."""

from dataclasses import dataclass
from typing import Any


@dataclass
class LoadProfile:
    requests_per_second: float
    duration: float
    pattern: str  # e.g. "constant", "ramp", "spike"


class TrafficSimulator:
    """Simulates traffic patterns against services."""

    def simulate(self, profile: LoadProfile) -> dict[str, Any]:
        raise NotImplementedError

    def get_load_profile(self, name: str) -> LoadProfile:
        raise NotImplementedError
