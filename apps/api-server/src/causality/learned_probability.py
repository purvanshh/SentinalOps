"""
Learned Probability Engine for SentinelOps Phase 7.

Replaces hardcoded probability weights (0.55, 0.20, 0.15, 0.10) with a
feature-based Bayesian updating system that learns from evidence characteristics.

Features extracted per hypothesis:
    - evidence_count: number of supporting evidence items
    - graph_depth: causal chain depth from graph traversal
    - historical_similarity: similarity to past confirmed incidents
    - deployment_distance: temporal gap between deployment and symptom
    - dependency_overlap: service dependency graph overlap
    - contradiction_count: number of contradicting evidence items
    - counterfactual_match: fraction of expected symptoms observed

Pipeline:
    Features → Prior Estimation → Bayesian Update → Calibrated Confidence
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class HypothesisFeatures:
    """Feature vector extracted for a single hypothesis."""

    hypothesis_id: str
    evidence_count: int = 0
    graph_depth: int = 0
    historical_similarity: float = 0.0
    deployment_distance_minutes: float = -1.0
    dependency_overlap: float = 0.0
    contradiction_count: int = 0
    counterfactual_match: float = 0.0
    evidence_quality_mean: float = 0.5
    mechanism_frequency: float = 0.1

    def to_dict(self) -> dict[str, float]:
        return {
            "evidence_count": float(self.evidence_count),
            "graph_depth": float(self.graph_depth),
            "historical_similarity": self.historical_similarity,
            "deployment_distance_minutes": self.deployment_distance_minutes,
            "dependency_overlap": self.dependency_overlap,
            "contradiction_count": float(self.contradiction_count),
            "counterfactual_match": self.counterfactual_match,
            "evidence_quality_mean": self.evidence_quality_mean,
            "mechanism_frequency": self.mechanism_frequency,
        }


# Default feature importance weights — learned over time from operator feedback
_DEFAULT_FEATURE_WEIGHTS: Dict[str, float] = {
    "evidence_count": 0.15,
    "graph_depth": 0.10,
    "historical_similarity": 0.20,
    "deployment_distance_minutes": 0.10,
    "dependency_overlap": 0.10,
    "contradiction_count": -0.15,
    "counterfactual_match": 0.15,
    "evidence_quality_mean": 0.10,
    "mechanism_frequency": 0.05,
}


@dataclass
class BayesianUpdate:
    """Records a single Bayesian update step."""

    prior: float
    likelihood: float
    posterior: float
    feature_contributions: Dict[str, float] = field(default_factory=dict)


class LearnedProbabilityEngine:
    """
    Feature-based Bayesian probability engine.

    Instead of fixed weights, computes hypothesis probabilities by:
    1. Extracting feature vectors for each hypothesis
    2. Computing a prior from mechanism frequency
    3. Computing likelihood from weighted feature scores
    4. Applying Bayes' rule with normalization
    """

    def __init__(
        self,
        feature_weights: Dict[str, float] | None = None,
    ) -> None:
        self.weights = feature_weights or dict(_DEFAULT_FEATURE_WEIGHTS)
        self._update_history: List[BayesianUpdate] = []

    def extract_features(
        self,
        hypothesis_id: str,
        candidate: Any,
        evidence_items: list[dict[str, Any]] | None = None,
        graph_depth: int = 0,
        historical_similarity: float = 0.0,
        counterfactual_match: float = 0.0,
        evidence_quality_mean: float = 0.5,
    ) -> HypothesisFeatures:
        """Extract a feature vector from a candidate hypothesis and its context."""
        supporting = getattr(candidate, "evidence_support", []) or []
        contradicting = getattr(candidate, "evidence_against", []) or []
        mechanism = getattr(candidate, "mechanism_type", "unknown") or "unknown"

        # Mechanism frequency prior (how common is this failure type)
        mechanism_priors = {
            "deployment_error": 0.25,
            "resource_exhaustion": 0.20,
            "cascade_failure": 0.15,
            "configuration_drift": 0.12,
            "dependency_failure": 0.15,
            "network_partition": 0.05,
            "data_corruption": 0.03,
            "unknown": 0.05,
        }

        return HypothesisFeatures(
            hypothesis_id=hypothesis_id,
            evidence_count=len(supporting),
            graph_depth=graph_depth,
            historical_similarity=historical_similarity,
            deployment_distance_minutes=-1.0,
            dependency_overlap=0.0,
            contradiction_count=len(contradicting),
            counterfactual_match=counterfactual_match,
            evidence_quality_mean=evidence_quality_mean,
            mechanism_frequency=mechanism_priors.get(mechanism, 0.05),
        )

    def compute_probability(
        self,
        features: HypothesisFeatures,
    ) -> BayesianUpdate:
        """Compute a Bayesian-updated probability for a single hypothesis."""
        prior = max(0.01, features.mechanism_frequency)

        # Compute likelihood from weighted features
        feature_dict = features.to_dict()
        contributions: Dict[str, float] = {}
        raw_likelihood = 0.0

        for feat_name, weight in self.weights.items():
            value = feature_dict.get(feat_name, 0.0)

            # Normalize certain features
            if feat_name == "evidence_count":
                value = min(1.0, value / 5.0)
            elif feat_name == "graph_depth":
                value = min(1.0, value / 5.0)
            elif feat_name == "deployment_distance_minutes":
                if value < 0:
                    value = 0.0  # No deployment context
                else:
                    value = max(0.0, 1.0 - (value / 60.0))  # Closer = higher
            elif feat_name == "contradiction_count":
                value = min(1.0, value / 3.0)

            contribution = weight * value
            contributions[feat_name] = round(contribution, 4)
            raw_likelihood += contribution

        # Sigmoid activation for likelihood
        likelihood = 1.0 / (1.0 + math.exp(-5.0 * (raw_likelihood - 0.3)))

        # Bayes update: P(H|E) ∝ P(E|H) * P(H)
        posterior = likelihood * prior

        update = BayesianUpdate(
            prior=round(prior, 4),
            likelihood=round(likelihood, 4),
            posterior=round(posterior, 4),
            feature_contributions=contributions,
        )
        self._update_history.append(update)
        return update

    def rank_hypotheses(
        self,
        feature_list: List[HypothesisFeatures],
    ) -> List[tuple[str, float]]:
        """Rank multiple hypotheses by their Bayesian posteriors."""
        updates = [(f.hypothesis_id, self.compute_probability(f)) for f in feature_list]

        # Normalize posteriors to sum to 1
        total = sum(u.posterior for _, u in updates)
        if total < 1e-9:
            total = 1.0

        ranked = [
            (hid, round(u.posterior / total, 4))
            for hid, u in updates
        ]
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked

    def update_weights(self, feedback: Dict[str, float]) -> None:
        """Update feature weights based on operator feedback (online learning)."""
        learning_rate = 0.05
        for feat_name, correction in feedback.items():
            if feat_name in self.weights:
                self.weights[feat_name] += learning_rate * correction
                self.weights[feat_name] = max(-1.0, min(1.0, self.weights[feat_name]))

    @property
    def update_history(self) -> List[BayesianUpdate]:
        return list(self._update_history)
