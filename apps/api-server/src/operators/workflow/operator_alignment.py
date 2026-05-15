"""
operator_alignment.py — Phase 49 Commit 5

Operator alignment benchmarking: measures how well an operator's decisions
align with AI-generated recommendations across acceptance, escalation, and
remediation dimensions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AlignmentBand(Enum):
    WELL_ALIGNED = "WELL_ALIGNED"
    GENERALLY_ALIGNED = "GENERALLY_ALIGNED"
    MISALIGNED = "MISALIGNED"
    ADVERSARIAL = "ADVERSARIAL"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class AlignmentMetrics:
    operator_id: str
    # Accepted recommendations / total recommendations
    recommendation_acceptance_rate: float
    # Overrides with rationale / total overrides
    justified_override_rate: float
    # Rejections / total recommendations
    operator_disagreement_rate: float
    # Overrides issued >5 min after recommendation / total overrides
    delayed_override_rate: float
    # Correct escalations / total escalations
    # (correct = L3+ recommended and actually resolved at L3+)
    escalation_accuracy: float
    # Rollbacks triggered / total remediations
    remediation_regret_rate: float


@dataclass
class OperatorAlignmentReport:
    operator_id: str
    metrics: AlignmentMetrics
    alignment_band: AlignmentBand
    alignment_score: float  # 0.0 – 1.0 composite
    recommendations_reviewed: int
    overrides_total: int
    remediation_regret_count: int


# ---------------------------------------------------------------------------
# Benchmark class
# ---------------------------------------------------------------------------


class OperatorAlignmentBenchmark:
    """Computes per-operator alignment metrics and classifies into bands."""

    def benchmark(
        self,
        operator_id: str,
        recommendations_reviewed: int,
        accepted: int,
        overrides_total: int,
        justified_overrides: int,
        delayed_overrides: int,
        escalations_total: int,
        correct_escalations: int,
        remediations_total: int,
        rollbacks_triggered: int,
    ) -> OperatorAlignmentReport:
        # Guard all divisions against zero-denominator
        acceptance_rate = accepted / max(recommendations_reviewed, 1)
        justified_override_rate = justified_overrides / max(overrides_total, 1)
        disagreement_rate = (recommendations_reviewed - accepted) / max(recommendations_reviewed, 1)
        delayed_override_rate = delayed_overrides / max(overrides_total, 1)
        escalation_accuracy = correct_escalations / max(escalations_total, 1)
        remediation_regret_rate = rollbacks_triggered / max(remediations_total, 1)

        metrics = AlignmentMetrics(
            operator_id=operator_id,
            recommendation_acceptance_rate=acceptance_rate,
            justified_override_rate=justified_override_rate,
            operator_disagreement_rate=disagreement_rate,
            delayed_override_rate=delayed_override_rate,
            escalation_accuracy=escalation_accuracy,
            remediation_regret_rate=remediation_regret_rate,
        )

        # Composite alignment score
        alignment_score = (
            0.30 * acceptance_rate
            + 0.20 * (1.0 - disagreement_rate)
            + 0.20 * escalation_accuracy
            + 0.15 * (1.0 - remediation_regret_rate)
            + 0.15 * justified_override_rate
        )
        # Clamp to [0, 1] for safety
        alignment_score = max(0.0, min(1.0, alignment_score))

        band = self._classify_band(alignment_score)

        return OperatorAlignmentReport(
            operator_id=operator_id,
            metrics=metrics,
            alignment_band=band,
            alignment_score=alignment_score,
            recommendations_reviewed=recommendations_reviewed,
            overrides_total=overrides_total,
            remediation_regret_count=rollbacks_triggered,
        )

    # ------------------------------------------------------------------

    @staticmethod
    def _classify_band(score: float) -> AlignmentBand:
        if score >= 0.75:
            return AlignmentBand.WELL_ALIGNED
        if score >= 0.55:
            return AlignmentBand.GENERALLY_ALIGNED
        if score >= 0.35:
            return AlignmentBand.MISALIGNED
        return AlignmentBand.ADVERSARIAL
