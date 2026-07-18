from __future__ import annotations

from agents.rca_structured import CandidateCause
from knowledge.graph_schema import EvidenceKnowledgeGraph
from verification.expectation_library import ExpectationLibrary


class CounterfactualValidator:
    """Validates candidate root causes against observed EKG node types and symptoms."""

    def __init__(self) -> None:
        self.library = ExpectationLibrary()

    def validate_candidates(
        self,
        candidates: list[CandidateCause],
        graph: EvidenceKnowledgeGraph,
    ) -> list[CandidateCause]:
        # Collect observed node types and description keywords in the graph
        observed_types = {n.type.value for n in graph.nodes}
        observed_descriptions = " ".join([n.description.lower() for n in graph.nodes])

        for candidate in candidates:
            exp = self.library.get_expectations(candidate.mechanism_type)
            if not exp:
                continue

            penalty = 0.0
            reward = 0.0

            # 1. Check if required node types are present in the evidence graph
            required_types = exp.get("required_node_types", set())
            missing_types = required_types - observed_types
            if missing_types:
                # Penalize based on missing structural node types
                penalty += 0.25 * len(missing_types)

            # 2. Check if expected keywords match observed descriptions
            expected_keywords = exp.get("expected_keywords", [])
            matched_keywords = [kw for kw in expected_keywords if kw in observed_descriptions]
            if matched_keywords:
                reward += 0.15 * (len(matched_keywords) / len(expected_keywords))
            else:
                penalty += 0.10

            # Calibrate confidence score
            original_confidence = candidate.confidence
            calibrated = min(1.0, max(0.01, original_confidence + reward - penalty))
            candidate.confidence = round(calibrated, 4)

        return candidates
