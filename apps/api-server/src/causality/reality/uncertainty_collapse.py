"""
Uncertainty collapse prevention for Phase 48 operational realism.

"Uncertainty collapse" happens when a system narrows from multiple
plausible explanations to a single attribution prematurely — before
the evidence actually supports it.

This module guards against:
  - Over-specific attribution with insufficient evidence
  - Confidence higher than the evidence supports
  - Ignoring competing explanations under time pressure
  - Claiming certainty to appease operators
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class CollapseRisk:
    """Describes a risk of premature uncertainty collapse."""

    risk_code: str
    description: str
    severity: str  # "low" | "medium" | "high"
    suggested_action: str


@dataclass
class CollapseGuardReport:
    risks: list[CollapseRisk]
    collapse_risk_score: float  # 0.0 = safe, 1.0 = high collapse risk
    recommended_max_confidence: float
    should_hold_back_attribution: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "collapse_risk_score": round(self.collapse_risk_score, 4),
            "recommended_max_confidence": round(self.recommended_max_confidence, 4),
            "should_hold_back_attribution": self.should_hold_back_attribution,
            "risk_count": len(self.risks),
            "risks": [
                {
                    "code": r.risk_code,
                    "severity": r.severity,
                    "description": r.description,
                    "action": r.suggested_action,
                }
                for r in self.risks
            ],
        }


class UncertaintyCollapseGuard:
    """
    Checks a proposed attribution for signs of premature collapse.

    Usage:
        guard = UncertaintyCollapseGuard()
        report = guard.check(
            proposed_confidence=0.85,
            evidence_count=2,
            hypothesis_count=4,
            top_gap=0.08,
            telemetry_completeness=0.4,
        )
    """

    _HIGH_RISK_THRESHOLD = 0.60
    _MAX_SAFE_EVIDENCE = 3  # evidence items needed for high confidence
    _SAFE_GAP = 0.20  # gap between top hypotheses needed for safe attribution

    def check(
        self,
        proposed_confidence: float,
        evidence_count: int,
        hypothesis_count: int,
        top_gap: float,
        telemetry_completeness: float,
    ) -> CollapseGuardReport:
        risks: list[CollapseRisk] = []

        # Risk 1: high confidence with sparse evidence
        if proposed_confidence > 0.70 and evidence_count < self._MAX_SAFE_EVIDENCE:
            risks.append(
                CollapseRisk(
                    risk_code="overconfident_sparse_evidence",
                    description=(
                        f"Confidence {proposed_confidence:.2f} claimed with only "
                        f"{evidence_count} evidence items"
                    ),
                    severity="high",
                    suggested_action=(
                        "Gather at least 3 corroborating evidence items "
                        "before claiming >70% confidence"
                    ),
                )
            )

        # Risk 2: ignoring competing hypotheses (small gap between top hypotheses)
        if hypothesis_count >= 2 and top_gap < self._SAFE_GAP:
            risks.append(
                CollapseRisk(
                    risk_code="competing_hypotheses_unresolved",
                    description=(
                        f"Top two hypotheses separated by only {top_gap:.2f}; "
                        f"attribution is premature"
                    ),
                    severity="medium",
                    suggested_action="Surface competing hypotheses to operator before committing",
                )
            )

        # Risk 3: attributing with poor telemetry
        if proposed_confidence > 0.60 and telemetry_completeness < 0.50:
            risks.append(
                CollapseRisk(
                    risk_code="attribution_with_poor_telemetry",
                    description=(
                        f"Attributing cause with telemetry completeness "
                        f"{telemetry_completeness:.2f}"
                    ),
                    severity="high",
                    suggested_action=(
                        "Improve telemetry completeness above 50% before attribution"
                    ),
                )
            )

        # Risk 4: single hypothesis (no alternatives considered)
        if hypothesis_count <= 1 and proposed_confidence > 0.50:
            risks.append(
                CollapseRisk(
                    risk_code="single_hypothesis_no_alternatives",
                    description="Only one hypothesis considered — alternatives not evaluated",
                    severity="medium",
                    suggested_action="Generate at least 2 alternative explanations",
                )
            )

        # Compute collapse risk score
        severity_weights = {"high": 0.40, "medium": 0.20, "low": 0.10}
        raw_score = sum(severity_weights.get(r.severity, 0.10) for r in risks)
        collapse_risk = min(1.0, raw_score)

        # Recommended max confidence (lower with more risks)
        recommended_max = max(0.20, proposed_confidence - collapse_risk * 0.40)
        should_hold_back = collapse_risk >= self._HIGH_RISK_THRESHOLD

        return CollapseGuardReport(
            risks=risks,
            collapse_risk_score=round(collapse_risk, 4),
            recommended_max_confidence=round(recommended_max, 4),
            should_hold_back_attribution=should_hold_back,
        )
