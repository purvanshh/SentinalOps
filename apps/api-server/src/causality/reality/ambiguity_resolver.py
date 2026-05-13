"""
Causal ambiguity resolver for Phase 48 operational realism.

Determines whether causal attribution is stable and whether competing
explanations remain unresolved. The system should prefer:
  "uncertain but honest" over "confident but wrong"

CausalRealityState values:
  STABLE_CAUSE            — single dominant cause with high confidence
  COMPETING_CAUSES        — multiple plausible causes, unresolved
  INSUFFICIENT_EVIDENCE   — not enough signals to attribute any cause
  TEMPORALLY_UNSTABLE     — causal chain depends on timestamp ordering
  OBSERVATION_CONFLICT    — contradictory signals prevent attribution
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class CausalRealityState(str, Enum):
    STABLE_CAUSE = "stable_cause"
    COMPETING_CAUSES = "competing_causes"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    TEMPORALLY_UNSTABLE = "temporally_unstable"
    OBSERVATION_CONFLICT = "observation_conflict"


_STATE_CONFIDENCE_CAP: dict[CausalRealityState, float] = {
    CausalRealityState.STABLE_CAUSE: 0.95,
    CausalRealityState.COMPETING_CAUSES: 0.60,
    CausalRealityState.INSUFFICIENT_EVIDENCE: 0.35,
    CausalRealityState.TEMPORALLY_UNSTABLE: 0.50,
    CausalRealityState.OBSERVATION_CONFLICT: 0.40,
}


@dataclass
class CausalAmbiguityReport:
    state: CausalRealityState
    dominant_cause: str | None
    competing_causes: list[str]
    evidence_count: int
    confidence_cap: float  # max allowable confidence given the state
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "dominant_cause": self.dominant_cause,
            "competing_causes": self.competing_causes,
            "evidence_count": self.evidence_count,
            "confidence_cap": round(self.confidence_cap, 4),
            "explanation": self.explanation,
        }

    @property
    def is_stable(self) -> bool:
        return self.state == CausalRealityState.STABLE_CAUSE

    @property
    def should_refuse_attribution(self) -> bool:
        return self.state in (
            CausalRealityState.INSUFFICIENT_EVIDENCE,
            CausalRealityState.OBSERVATION_CONFLICT,
        )


class AmbiguityResolver:
    """
    Determines the causal reality state from a set of candidate hypotheses.

    Each hypothesis is a dict with:
      {"mechanism": str, "confidence": float, "supporting_evidence": list[str]}
    """

    _DOMINANT_THRESHOLD = 0.60  # leading cause must be >60% to be STABLE
    _COMPETING_GAP = 0.15  # gap < 15% between top two = COMPETING
    _MIN_EVIDENCE_COUNT = 2  # fewer than 2 evidence items = INSUFFICIENT
    _MIN_CONFIDENCE = 0.25  # overall top confidence < 25% = INSUFFICIENT

    def resolve(
        self,
        hypotheses: list[dict[str, Any]],
        has_temporal_instability: bool = False,
        has_observation_conflict: bool = False,
    ) -> CausalAmbiguityReport:
        if not hypotheses:
            return CausalAmbiguityReport(
                state=CausalRealityState.INSUFFICIENT_EVIDENCE,
                dominant_cause=None,
                competing_causes=[],
                evidence_count=0,
                confidence_cap=_STATE_CONFIDENCE_CAP[CausalRealityState.INSUFFICIENT_EVIDENCE],
                explanation="No hypotheses provided",
            )

        sorted_hyps = sorted(
            hypotheses,
            key=lambda h: float(h.get("confidence", 0.0)),
            reverse=True,
        )

        top = sorted_hyps[0]
        top_conf = float(top.get("confidence", 0.0))
        top_mechanism = top.get("mechanism", "unknown")
        evidence_count = len(top.get("supporting_evidence", []))

        # Observation conflict overrides everything
        if has_observation_conflict:
            return CausalAmbiguityReport(
                state=CausalRealityState.OBSERVATION_CONFLICT,
                dominant_cause=None,
                competing_causes=[h.get("mechanism", "") for h in sorted_hyps],
                evidence_count=evidence_count,
                confidence_cap=_STATE_CONFIDENCE_CAP[CausalRealityState.OBSERVATION_CONFLICT],
                explanation="Contradictory observations prevent causal attribution",
            )

        # Temporal instability
        if has_temporal_instability:
            return CausalAmbiguityReport(
                state=CausalRealityState.TEMPORALLY_UNSTABLE,
                dominant_cause=top_mechanism,
                competing_causes=[h.get("mechanism", "") for h in sorted_hyps[1:]],
                evidence_count=evidence_count,
                confidence_cap=_STATE_CONFIDENCE_CAP[CausalRealityState.TEMPORALLY_UNSTABLE],
                explanation="Causal chain is sensitive to timestamp ordering",
            )

        # Insufficient evidence
        if top_conf < self._MIN_CONFIDENCE or evidence_count < self._MIN_EVIDENCE_COUNT:
            return CausalAmbiguityReport(
                state=CausalRealityState.INSUFFICIENT_EVIDENCE,
                dominant_cause=None,
                competing_causes=[h.get("mechanism", "") for h in sorted_hyps],
                evidence_count=evidence_count,
                confidence_cap=_STATE_CONFIDENCE_CAP[CausalRealityState.INSUFFICIENT_EVIDENCE],
                explanation=(
                    f"Insufficient evidence: top_conf={top_conf:.2f}, "
                    f"evidence_items={evidence_count}"
                ),
            )

        # Competing causes: gap between top two is too small
        if len(sorted_hyps) >= 2:
            second_conf = float(sorted_hyps[1].get("confidence", 0.0))
            if top_conf - second_conf < self._COMPETING_GAP:
                return CausalAmbiguityReport(
                    state=CausalRealityState.COMPETING_CAUSES,
                    dominant_cause=top_mechanism,
                    competing_causes=[h.get("mechanism", "") for h in sorted_hyps[1:]],
                    evidence_count=evidence_count,
                    confidence_cap=_STATE_CONFIDENCE_CAP[CausalRealityState.COMPETING_CAUSES],
                    explanation=(
                        f"Competing causes: top={top_conf:.2f}, "
                        f"second={second_conf:.2f}, gap={top_conf - second_conf:.2f}"
                    ),
                )

        # Stable cause: dominant above threshold
        if top_conf >= self._DOMINANT_THRESHOLD:
            return CausalAmbiguityReport(
                state=CausalRealityState.STABLE_CAUSE,
                dominant_cause=top_mechanism,
                competing_causes=[h.get("mechanism", "") for h in sorted_hyps[1:]],
                evidence_count=evidence_count,
                confidence_cap=_STATE_CONFIDENCE_CAP[CausalRealityState.STABLE_CAUSE],
                explanation=f"Stable attribution: {top_mechanism} at {top_conf:.2f}",
            )

        # Default: competing causes (not high enough to be stable)
        return CausalAmbiguityReport(
            state=CausalRealityState.COMPETING_CAUSES,
            dominant_cause=top_mechanism,
            competing_causes=[h.get("mechanism", "") for h in sorted_hyps[1:]],
            evidence_count=evidence_count,
            confidence_cap=_STATE_CONFIDENCE_CAP[CausalRealityState.COMPETING_CAUSES],
            explanation=(
                f"Cause below dominant threshold: {top_conf:.2f} < {self._DOMINANT_THRESHOLD}"
            ),
        )
