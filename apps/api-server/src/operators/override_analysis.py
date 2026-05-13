"""
Override analysis for SentinelOps Phase 47.

Detects, categorizes, and summarizes cases where operators overrode
AI recommendations. Identifies patterns in override behavior across
mechanisms, operators, and confidence levels.
"""

from __future__ import annotations

from dataclasses import dataclass

from operators.intervention_tracker import OperatorIntervention


@dataclass
class OverridePattern:
    """A detected pattern in operator override behavior."""

    mechanism: str
    override_count: int
    total_interactions: int
    override_rate: float
    operators_involved: set[str]
    mean_ai_confidence: float
    is_systematic: bool  # True when override_rate >= 0.50

    def summary(self) -> str:
        return (
            f"mechanism={self.mechanism} "
            f"rate={self.override_rate:.2f} "
            f"systematic={self.is_systematic}"
        )


@dataclass
class OverrideReport:
    """Full analysis of override behavior across all interventions."""

    total_interventions: int
    total_overrides: int
    overall_override_rate: float
    systematic_mechanisms: list[str]
    by_mechanism: list[OverridePattern]
    high_confidence_overrides: int  # AI confidence >= 0.70 but operator overrode
    low_confidence_approvals: int  # AI confidence < 0.50 but operator approved
    top_overriding_operators: list[tuple[str, int]]  # (operator_id, override_count)


class OverrideAnalyzer:
    """
    Analyzes operator override patterns from a set of interventions.

    Identifies mechanisms with systematic disagreement, high-confidence
    override incidents, and per-operator override tendencies.
    """

    _SYSTEMATIC_THRESHOLD: float = 0.50
    _HIGH_CONFIDENCE_THRESHOLD: float = 0.70
    _LOW_CONFIDENCE_THRESHOLD: float = 0.50

    def analyze(self, interventions: list[OperatorIntervention]) -> OverrideReport:
        n = len(interventions)
        overrides = [iv for iv in interventions if iv.is_override]
        n_overrides = len(overrides)

        by_mechanism = self._analyze_by_mechanism(interventions)
        systematic = [p.mechanism for p in by_mechanism if p.is_systematic]

        high_conf_overrides = sum(
            1 for iv in overrides if iv.confidence_at_time >= self._HIGH_CONFIDENCE_THRESHOLD
        )
        low_conf_approvals = sum(
            1
            for iv in interventions
            if iv.is_approval and iv.confidence_at_time < self._LOW_CONFIDENCE_THRESHOLD
        )

        op_counts: dict[str, int] = {}
        for iv in overrides:
            op_counts[iv.operator_id] = op_counts.get(iv.operator_id, 0) + 1
        top_ops = sorted(op_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        return OverrideReport(
            total_interventions=n,
            total_overrides=n_overrides,
            overall_override_rate=n_overrides / n if n > 0 else 0.0,
            systematic_mechanisms=systematic,
            by_mechanism=by_mechanism,
            high_confidence_overrides=high_conf_overrides,
            low_confidence_approvals=low_conf_approvals,
            top_overriding_operators=top_ops,
        )

    def mechanisms_with_high_override(
        self, interventions: list[OperatorIntervention], min_rate: float = 0.40
    ) -> list[str]:
        patterns = self._analyze_by_mechanism(interventions)
        return [p.mechanism for p in patterns if p.override_rate >= min_rate]

    def operator_override_rates(
        self, interventions: list[OperatorIntervention]
    ) -> dict[str, float]:
        by_op: dict[str, list[OperatorIntervention]] = {}
        for iv in interventions:
            by_op.setdefault(iv.operator_id, []).append(iv)

        rates: dict[str, float] = {}
        for op, ivs in by_op.items():
            n = len(ivs)
            overrides = sum(1 for iv in ivs if iv.is_override)
            rates[op] = overrides / n if n > 0 else 0.0
        return rates

    # ------------------------------------------------------------------

    def _analyze_by_mechanism(
        self, interventions: list[OperatorIntervention]
    ) -> list[OverridePattern]:
        by_mech: dict[str, list[OperatorIntervention]] = {}
        for iv in interventions:
            mech = iv.target_mechanism or "unknown"
            by_mech.setdefault(mech, []).append(iv)

        patterns: list[OverridePattern] = []
        for mech, ivs in by_mech.items():
            n = len(ivs)
            overrides = [iv for iv in ivs if iv.is_override]
            n_overrides = len(overrides)
            rate = n_overrides / n if n > 0 else 0.0
            mean_conf = (
                sum(iv.confidence_at_time for iv in overrides) / n_overrides
                if n_overrides > 0
                else 0.0
            )
            patterns.append(
                OverridePattern(
                    mechanism=mech,
                    override_count=n_overrides,
                    total_interactions=n,
                    override_rate=rate,
                    operators_involved={iv.operator_id for iv in ivs},
                    mean_ai_confidence=mean_conf,
                    is_systematic=rate >= self._SYSTEMATIC_THRESHOLD,
                )
            )
        return sorted(patterns, key=lambda p: p.override_rate, reverse=True)
