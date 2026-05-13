"""
Operational Semantic Engine for SentinelOps Phase 45.

Maps evidence collections into operational mechanism inferences.
Rather than pattern-matching on surface keywords, the engine scores evidence
against the failure mechanism ontology to infer WHAT operational mechanism
is most likely responsible for the observed behavior.

Key outputs:
  - primary inferred mechanism with confidence
  - alternative mechanisms ranked by plausibility
  - evidence-to-mechanism alignment summary
  - latent infrastructure state implications
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from semantics.ontology import FailureMechanism, FailureMechanismOntology


@dataclass
class MechanismScore:
    mechanism: FailureMechanism
    raw_score: float
    normalized_probability: float
    matched_keywords: list[str]
    supporting_evidence_keys: list[str]


@dataclass
class MechanismInference:
    """Result of semantic mechanism inference from evidence."""

    primary: MechanismScore | None
    alternatives: list[MechanismScore]
    combined_text: str
    latent_state_implications: list[str]
    mechanism_confidence: float
    inference_rationale: str

    @property
    def primary_mechanism_id(self) -> str | None:
        return self.primary.mechanism.mechanism_id if self.primary else None

    @property
    def primary_mechanism_name(self) -> str | None:
        return self.primary.mechanism.name if self.primary else None

    def to_hypothesis_prefix(self) -> str:
        """
        Return a mechanism-aware prefix for root-cause hypothesis text.
        Replaces the generic 'X is the most likely contributor to Y' template.
        """
        if self.primary is None:
            return ""
        mechanism = self.primary.mechanism
        return (
            f"Evidence suggests {mechanism.name.lower()} as the operational mechanism. "
            f"{mechanism.description}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "primary_mechanism_id": self.primary_mechanism_id,
            "primary_mechanism_name": self.primary_mechanism_name,
            "mechanism_confidence": round(self.mechanism_confidence, 4),
            "latent_state_implications": self.latent_state_implications,
            "inference_rationale": self.inference_rationale,
            "alternatives": [
                {
                    "mechanism_id": alt.mechanism.mechanism_id,
                    "name": alt.mechanism.name,
                    "normalized_probability": round(alt.normalized_probability, 4),
                }
                for alt in self.alternatives[:3]
            ],
        }


def _build_combined_text(evidence_items: list[dict[str, Any]], timed_events: list[Any]) -> str:
    parts: list[str] = []
    for item in evidence_items:
        for key in ("summary", "metric", "signature", "commit_summary", "description", "item_type"):
            value = item.get(key)
            if value:
                parts.append(str(value))
    for event in timed_events:
        summary = getattr(event, "summary", "") or ""
        item_type = getattr(event, "item_type", "") or ""
        if summary:
            parts.append(summary)
        if item_type:
            parts.append(item_type)
    return " ".join(parts)


def _extract_keywords_matched(
    mechanism: FailureMechanism, text: str
) -> list[str]:
    lower = text.lower()
    return [kw for kw in mechanism.symptom_keywords if kw in lower]


def _supporting_evidence_keys(
    mechanism: FailureMechanism, evidence_items: list[dict[str, Any]]
) -> list[str]:
    keys: list[str] = []
    for item in evidence_items:
        item_text = " ".join(
            str(v) for k, v in item.items()
            if k in ("summary", "metric", "signature", "description", "item_type")
        ).lower()
        if any(kw in item_text for kw in mechanism.symptom_keywords):
            keys.append(item.get("item_key", ""))
    return [k for k in keys if k]


def _normalize_probabilities(raw_scores: list[float]) -> list[float]:
    total = sum(raw_scores)
    if total <= 0:
        n = len(raw_scores)
        return [1.0 / n if n > 0 else 0.0] * n
    return [score / total for score in raw_scores]


class OperationalSemanticEngine:
    """
    Infers failure mechanisms from evidence collections.

    Scores evidence against the full failure mechanism ontology and returns
    a ranked list of inferred mechanisms with probabilities. This replaces
    surface-level keyword pattern matching with operational concept alignment.
    """

    def __init__(self, ontology: FailureMechanismOntology | None = None) -> None:
        self._ontology = ontology or FailureMechanismOntology()

    def infer_mechanism(
        self,
        evidence_items: list[dict[str, Any]],
        timed_events: list[Any],
        *,
        incident_type: str | None = None,
    ) -> MechanismInference:
        combined_text = _build_combined_text(evidence_items, timed_events)
        scored_mechanisms = self._ontology.score_mechanisms(combined_text)

        mechanism_scores: list[MechanismScore] = []
        for mechanism, raw_keyword_count in scored_mechanisms:
            matched = _extract_keywords_matched(mechanism, combined_text)
            supporting_keys = _supporting_evidence_keys(mechanism, evidence_items)

            # Base score from keyword matches
            raw_score = float(raw_keyword_count)

            # Boost if incident_type aligns with mechanism
            if incident_type and any(
                incident_type.replace("_", " ").lower() in cause.lower()
                for cause in mechanism.common_causes
            ):
                raw_score += 1.5

            # Boost for evidence key support
            raw_score += min(0.5 * len(supporting_keys), 2.0)

            if raw_score > 0:
                mechanism_scores.append(
                    MechanismScore(
                        mechanism=mechanism,
                        raw_score=raw_score,
                        normalized_probability=0.0,
                        matched_keywords=matched,
                        supporting_evidence_keys=supporting_keys,
                    )
                )

        # Normalize to probability distribution
        raw_values = [ms.raw_score for ms in mechanism_scores]
        normalized = _normalize_probabilities(raw_values)
        for index, ms in enumerate(mechanism_scores):
            ms.normalized_probability = normalized[index]

        primary = mechanism_scores[0] if mechanism_scores else None
        alternatives = mechanism_scores[1:] if len(mechanism_scores) > 1 else []

        # Mechanism confidence: how dominant is the top mechanism?
        if len(mechanism_scores) >= 2:
            confidence = mechanism_scores[0].normalized_probability
        elif mechanism_scores:
            confidence = 0.5 if mechanism_scores[0].raw_score > 0 else 0.0
        else:
            confidence = 0.0

        # Latent state implications from top mechanism
        latent_states: list[str] = []
        if primary:
            latent_states = list(primary.mechanism.latent_states)

        # Rationale
        if primary and primary.matched_keywords:
            rationale = (
                f"Evidence strongly aligns with '{primary.mechanism.name}' "
                f"based on: {', '.join(primary.matched_keywords[:4])}."
            )
        elif primary:
            rationale = (
                f"'{primary.mechanism.name}' selected as best-match mechanism "
                f"by incident type and evidence structure, but keyword evidence is weak."
            )
        else:
            rationale = "Insufficient evidence to identify an operational mechanism."

        return MechanismInference(
            primary=primary,
            alternatives=alternatives,
            combined_text=combined_text,
            latent_state_implications=latent_states,
            mechanism_confidence=round(confidence, 4),
            inference_rationale=rationale,
        )

    def build_mechanism_hypothesis_text(
        self,
        candidate_title: str,
        cause_service: str,
        affected_service: str,
        inference: MechanismInference | None,
    ) -> str:
        """
        Build a mechanism-aware hypothesis text.

        Replaces the generic template
        'X in service is the most likely contributor to the impact on Y'
        with an explanation that names the operational mechanism.
        """
        if inference is None or inference.primary is None:
            return (
                f"{candidate_title} in {cause_service} is the most likely contributor "
                f"to the impact observed on {affected_service}."
            )

        mechanism = inference.primary.mechanism
        if cause_service == affected_service:
            return (
                f"{mechanism.name} in {cause_service} likely explains the observed "
                f"degradation: {mechanism.description.rstrip('.')} "
                f"Evidence pattern: {candidate_title}."
            )
        return (
            f"{mechanism.name} in {cause_service} likely propagated to "
            f"{affected_service}. {mechanism.description.rstrip('.')} "
            f"Evidence pattern: {candidate_title}."
        )

    def build_mechanism_causal_chain(
        self,
        candidate_title: str,
        cause_service: str,
        affected_service: str,
        inference: MechanismInference | None,
    ) -> str:
        """Build a mechanism-aware causal chain description."""
        if inference is None or inference.primary is None:
            if cause_service == affected_service:
                return (
                    f"{candidate_title} -> degraded {affected_service} behavior "
                    f"-> user-facing impact"
                )
            return (
                f"{candidate_title} in {cause_service} -> "
                f"downstream impact on {affected_service}"
            )

        mechanism = inference.primary.mechanism
        latent = inference.latent_state_implications
        latent_str = " -> ".join(latent[:2]) if latent else "resource pressure"

        if cause_service == affected_service:
            return (
                f"{candidate_title} triggers {mechanism.mechanism_id.replace('_', ' ')} "
                f"-> {latent_str} -> degraded {affected_service} -> user-facing impact"
            )
        return (
            f"{candidate_title} in {cause_service} triggers "
            f"{mechanism.mechanism_id.replace('_', ' ')} -> {latent_str} "
            f"-> downstream impact on {affected_service}"
        )
