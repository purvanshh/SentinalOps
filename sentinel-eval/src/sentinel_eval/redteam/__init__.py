"""Red team adversarial evaluation."""

from dataclasses import dataclass
from typing import Any


@dataclass
class AdversarialScenario:
    name: str
    attack_type: str
    payload: dict[str, Any]


class RedTeamRunner:
    """Runs adversarial scenarios against the pipeline."""

    def run_scenarios(self, scenarios: list[AdversarialScenario]) -> list[dict[str, Any]]:
        raise NotImplementedError
