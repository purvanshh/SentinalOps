"""
Confidence penalty calculation for Phase 48 operational realism.

Aggregates observability gaps, integrity violations, and chaos signals
to produce a single root-cause confidence penalty that should be applied
before surfacing a hypothesis to operators.

The system should never claim high confidence when observability is poor.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from observability.reality.completeness_analyzer import CompletenessScore
from observability.reality.observability_gaps import GapReport
from observability.reality.telemetry_integrity import IntegrityReport

# Maximum penalty from each source
_MAX_COMPLETENESS_PENALTY = 0.30
_MAX_GAP_PENALTY = 0.30
_MAX_INTEGRITY_PENALTY = 0.20
_ABSOLUTE_MAX_PENALTY = 0.60


@dataclass
class PenaltyBreakdown:
    """Decomposed penalty contributions."""

    completeness_penalty: float
    gap_penalty: float
    integrity_penalty: float
    total_penalty: float
    penalised_confidence: float  # original_confidence - total_penalty, floored at 0.05
    should_refuse_attribution: bool  # True when penalised_confidence < 0.20

    def to_dict(self) -> dict[str, Any]:
        return {
            "completeness_penalty": round(self.completeness_penalty, 4),
            "gap_penalty": round(self.gap_penalty, 4),
            "integrity_penalty": round(self.integrity_penalty, 4),
            "total_penalty": round(self.total_penalty, 4),
            "penalised_confidence": round(self.penalised_confidence, 4),
            "should_refuse_attribution": self.should_refuse_attribution,
        }


class ConfidencePenaltyCalculator:
    """
    Computes a confidence penalty from observability signals.

    Usage:
        calc = ConfidencePenaltyCalculator()
        breakdown = calc.compute(original_conf, completeness, gap_report, integrity_report)
        adjusted_conf = breakdown.penalised_confidence
    """

    def compute(
        self,
        original_confidence: float,
        completeness: CompletenessScore,
        gap_report: GapReport,
        integrity_report: IntegrityReport,
    ) -> PenaltyBreakdown:
        # Completeness penalty: low completeness → high penalty
        completeness_penalty = min(
            _MAX_COMPLETENESS_PENALTY,
            _MAX_COMPLETENESS_PENALTY * (1.0 - completeness.overall),
        )

        # Gap penalty: directly from gap report
        gap_penalty = min(_MAX_GAP_PENALTY, gap_report.total_confidence_penalty)

        # Integrity penalty: inversely proportional to integrity score
        integrity_penalty = min(
            _MAX_INTEGRITY_PENALTY,
            _MAX_INTEGRITY_PENALTY * (1.0 - integrity_report.integrity_score),
        )

        total_penalty = min(
            _ABSOLUTE_MAX_PENALTY,
            completeness_penalty + gap_penalty + integrity_penalty,
        )

        penalised = max(0.05, original_confidence - total_penalty)
        refuse = penalised < 0.20

        return PenaltyBreakdown(
            completeness_penalty=round(completeness_penalty, 4),
            gap_penalty=round(gap_penalty, 4),
            integrity_penalty=round(integrity_penalty, 4),
            total_penalty=round(total_penalty, 4),
            penalised_confidence=round(penalised, 4),
            should_refuse_attribution=refuse,
        )

    def compute_from_events(
        self,
        original_confidence: float,
        events: list[dict[str, Any]],
    ) -> PenaltyBreakdown:
        """Convenience: compute all sub-reports from raw events."""
        from observability.reality.completeness_analyzer import CompletenessAnalyzer
        from observability.reality.observability_gaps import ObservabilityGapDetector
        from observability.reality.telemetry_integrity import TelemetryIntegrityChecker

        completeness = CompletenessAnalyzer().analyze(events)
        gaps = ObservabilityGapDetector().detect(events)
        integrity = TelemetryIntegrityChecker().check(events)
        return self.compute(original_confidence, completeness, gaps, integrity)
