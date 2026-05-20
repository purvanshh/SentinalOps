"""Scoring framework for evaluation."""

from abc import ABC, abstractmethod
from typing import Any


class Scorer(ABC):
    """Base scorer interface."""

    @abstractmethod
    def score(self, prediction: Any, ground_truth: Any) -> float: ...


class SafetyScorer(Scorer):
    def score(self, prediction: Any, ground_truth: Any) -> float:
        raise NotImplementedError


class CalibrationScorer(Scorer):
    def score(self, prediction: Any, ground_truth: Any) -> float:
        raise NotImplementedError


class GroundingScorer(Scorer):
    def score(self, prediction: Any, ground_truth: Any) -> float:
        raise NotImplementedError
