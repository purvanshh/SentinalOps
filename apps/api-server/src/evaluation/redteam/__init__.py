"""Adversarial red-team evaluation — tests system honesty under deceptive inputs."""

from .adversarial_scenarios import AdversarialScenario, ScenarioLibrary
from .realism_scores import AdversarialRealismScorer, RealismReport
from .redteam_evaluator import RedTeamEvaluator, RedTeamResult

__all__ = [
    "AdversarialScenario",
    "ScenarioLibrary",
    "RedTeamEvaluator",
    "RedTeamResult",
    "AdversarialRealismScorer",
    "RealismReport",
]
