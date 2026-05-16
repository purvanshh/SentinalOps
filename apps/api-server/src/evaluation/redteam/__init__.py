"""Adversarial red-team evaluation — tests system honesty under deceptive inputs."""

from .adversarial_scenarios import AdversarialScenario, ScenarioLibrary
from .redteam_evaluator import RedTeamEvaluator, RedTeamResult
from .realism_scores import AdversarialRealismScorer, RealismReport

__all__ = [
    "AdversarialScenario",
    "ScenarioLibrary",
    "RedTeamEvaluator",
    "RedTeamResult",
    "AdversarialRealismScorer",
    "RealismReport",
]
