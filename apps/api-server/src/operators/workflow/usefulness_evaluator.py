"""
usefulness_evaluator.py — Phase 49 Commit 6

Evaluates the overall operational usefulness of an AI incident-response
session by combining workflow quality, operator alignment, escalation
burden, cognitive load, trust stability, remediation usefulness, and
explainability quality into a single composite score.
"""

from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Report dataclass
# ---------------------------------------------------------------------------


@dataclass
class OperationalUsefulnessReport:
    session_id: str
    workflow_quality: float  # 0.0–1.0
    operator_alignment: float  # 0.0–1.0
    escalation_burden: float  # 0.0–1.0 (higher = more burden)
    recommendation_quality: float  # 0.0–1.0
    cognitive_load_score: float  # 0.0–1.0 (higher = more load)
    trust_stability: float  # 0.0–1.0
    remediation_usefulness: float  # 0.0–1.0
    explainability_quality: float  # 0.0–1.0
    overall_usefulness: float  # weighted composite
    is_operationally_useful: bool  # True if overall_usefulness >= 0.55
    improvement_areas: list[str]  # dimensions scoring below 0.50


# ---------------------------------------------------------------------------
# Evaluator class
# ---------------------------------------------------------------------------


class OperationalUsefulnessEvaluator:
    """
    Computes a weighted operational usefulness composite and identifies
    dimensions that fall below the 0.50 quality threshold.

    Weights
    -------
    workflow_quality       0.15
    operator_alignment     0.15
    (1 - escalation_burden) 0.10
    recommendation_quality  0.15
    (1 - cognitive_load)    0.10
    trust_stability         0.15
    remediation_usefulness  0.10
    explainability_quality  0.10
    """

    # Threshold below which a dimension is flagged as an improvement area.
    _IMPROVEMENT_THRESHOLD: float = 0.50
    # Threshold above which the session is considered operationally useful.
    _USEFULNESS_THRESHOLD: float = 0.55

    def evaluate(
        self,
        session_id: str,
        workflow_quality: float,
        operator_alignment: float,
        escalation_burden: float,
        recommendation_quality: float,
        cognitive_load_score: float,
        trust_stability: float,
        remediation_usefulness: float,
        explainability_quality: float,
    ) -> OperationalUsefulnessReport:
        overall_usefulness = (
            0.15 * workflow_quality
            + 0.15 * operator_alignment
            + 0.10 * (1.0 - escalation_burden)
            + 0.15 * recommendation_quality
            + 0.10 * (1.0 - cognitive_load_score)
            + 0.15 * trust_stability
            + 0.10 * remediation_usefulness
            + 0.10 * explainability_quality
        )

        # Identify dimensions whose effective contribution falls below threshold.
        improvement_areas: list[str] = []
        _t = self._IMPROVEMENT_THRESHOLD

        if workflow_quality < _t:
            improvement_areas.append("workflow_quality")
        if operator_alignment < _t:
            improvement_areas.append("operator_alignment")
        # For burden/load fields the useful value is the inverse.
        if (1.0 - escalation_burden) < _t:
            improvement_areas.append("escalation_burden")
        if recommendation_quality < _t:
            improvement_areas.append("recommendation_quality")
        if (1.0 - cognitive_load_score) < _t:
            improvement_areas.append("cognitive_load_score")
        if trust_stability < _t:
            improvement_areas.append("trust_stability")
        if remediation_usefulness < _t:
            improvement_areas.append("remediation_usefulness")
        if explainability_quality < _t:
            improvement_areas.append("explainability_quality")

        is_operationally_useful = overall_usefulness >= self._USEFULNESS_THRESHOLD

        return OperationalUsefulnessReport(
            session_id=session_id,
            workflow_quality=workflow_quality,
            operator_alignment=operator_alignment,
            escalation_burden=escalation_burden,
            recommendation_quality=recommendation_quality,
            cognitive_load_score=cognitive_load_score,
            trust_stability=trust_stability,
            remediation_usefulness=remediation_usefulness,
            explainability_quality=explainability_quality,
            overall_usefulness=overall_usefulness,
            is_operationally_useful=is_operationally_useful,
            improvement_areas=improvement_areas,
        )
