"""
Causal stability analysis for Phase 48 operational realism.

A causal attribution is "stable" if the same conclusion would be reached
under small perturbations to the evidence or event ordering.

Instability is detected when:
  - Removing any single evidence item changes the top hypothesis
  - Reordering two events changes the attribution
  - The top confidence would drop below a threshold under evidence loss
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class StabilityProbe:
    """Result of one perturbation test."""

    perturbation: str
    stable: bool
    original_top: str
    perturbed_top: str | None
    confidence_delta: float


@dataclass
class CausalStabilityReport:
    probes: list[StabilityProbe]
    is_stable: bool
    stability_score: float  # fraction of probes that preserved attribution
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_stable": self.is_stable,
            "stability_score": round(self.stability_score, 4),
            "probe_count": len(self.probes),
            "explanation": self.explanation,
        }


class CausalStabilityAnalyzer:
    """
    Tests causal attribution stability via leave-one-out evidence probes.

    For each evidence item supporting the top hypothesis, this analyzer
    checks whether removing it changes the conclusion.
    """

    _STABILITY_THRESHOLD = 0.70  # ≥70% of probes must preserve attribution

    def analyze(
        self,
        hypotheses: list[dict[str, Any]],
    ) -> CausalStabilityReport:
        """
        Run leave-one-out probes on the evidence supporting the top hypothesis.

        Each hypothesis should have: {"mechanism": str, "confidence": float,
        "supporting_evidence": list[str]}
        """
        if not hypotheses:
            return CausalStabilityReport(
                probes=[],
                is_stable=False,
                stability_score=0.0,
                explanation="No hypotheses to test",
            )

        sorted_h = sorted(
            hypotheses,
            key=lambda h: float(h.get("confidence", 0.0)),
            reverse=True,
        )
        top = sorted_h[0]
        top_mechanism = top.get("mechanism", "unknown")
        top_conf = float(top.get("confidence", 0.0))
        evidence = top.get("supporting_evidence", [])

        if len(sorted_h) < 2:
            return CausalStabilityReport(
                probes=[],
                is_stable=True,
                stability_score=1.0,
                explanation="Only one hypothesis; trivially stable but alternatives not tested",
            )

        second = sorted_h[1]
        second_conf = float(second.get("confidence", 0.0))
        second_mechanism = second.get("mechanism", "unknown")
        gap = top_conf - second_conf

        probes: list[StabilityProbe] = []

        # Probe: what if each evidence item is removed?
        ev_weight = (top_conf / max(1, len(evidence))) if evidence else 0.0
        for ev_item in evidence:
            hypothetical_conf = top_conf - ev_weight
            still_top = hypothetical_conf > second_conf
            probes.append(
                StabilityProbe(
                    perturbation=f"remove_evidence:{ev_item[:40]}",
                    stable=still_top,
                    original_top=top_mechanism,
                    perturbed_top=top_mechanism if still_top else second_mechanism,
                    confidence_delta=-ev_weight,
                )
            )

        # Probe: what if clock skew reorders the first two events?
        probes.append(
            StabilityProbe(
                perturbation="reorder_first_two_events",
                stable=gap >= 0.20,
                original_top=top_mechanism,
                perturbed_top=second_mechanism if gap < 0.20 else None,
                confidence_delta=0.0,
            )
        )

        stable_count = sum(1 for p in probes if p.stable)
        stability_score = stable_count / len(probes) if probes else 0.0
        is_stable = stability_score >= self._STABILITY_THRESHOLD

        explanation = (
            f"Attribution stable under {stable_count}/{len(probes)} perturbation probes "
            f"(gap={gap:.2f})"
        )

        return CausalStabilityReport(
            probes=probes,
            is_stable=is_stable,
            stability_score=round(stability_score, 4),
            explanation=explanation,
        )
