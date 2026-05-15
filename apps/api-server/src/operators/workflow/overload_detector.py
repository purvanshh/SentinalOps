"""
Cognitive Overload Detector for SentinelOps Phase 49.

Tracks the total cognitive load an operator carries at any given moment by
aggregating five independent cognitive load signals into a single score and
classifying the result into an OverloadState.  When the operator is OVERLOADED
or SATURATED the system automatically suppresses recommendation output to
prevent further degradation of decision quality.

Signals and weights
-------------------
  active_ambiguity        weight=0.25  saturation at 5 ambiguous incidents
  unresolved_pressure     weight=0.20  saturation at 10 open incidents
  alert_density           weight=0.20  0.0–1.0 pre-normalised
  explanation_complexity  weight=0.20  0.0–1.0 pre-normalised
  contradictory_signals   weight=0.15  saturation at 5 contradictory signals

CognitiveLoadAnalyzer.analyze() returns a CognitiveLoadReport.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class OverloadState(Enum):
    """Qualitative cognitive load classification derived from total load score."""

    NORMAL = "NORMAL"  # total < 0.30
    ELEVATED = "ELEVATED"  # 0.30 <= total < 0.55
    OVERLOADED = "OVERLOADED"  # 0.55 <= total < 0.80
    SATURATED = "SATURATED"  # total >= 0.80


@dataclass
class CognitiveLoadSignal:
    """A single cognitive load signal with its normalised value and contribution."""

    signal_name: str  # short identifier, e.g. "active_ambiguity"
    value: float  # normalised to [0.0, 1.0]
    weight: float  # importance weight in [0.0, 1.0]
    contribution: float  # weight * value


@dataclass
class CognitiveLoadReport:
    """Full cognitive load report produced by CognitiveLoadAnalyzer.analyze()."""

    operator_id: str
    signals: list[CognitiveLoadSignal]
    total_cognitive_load: float  # 0.0–1.0
    state: OverloadState
    active_ambiguity_count: int
    unresolved_count: int
    alert_density: float
    explanation_complexity: float
    contradictory_signal_count: int
    recommendation_suppression_active: bool  # True if state is OVERLOADED or SATURATED


class CognitiveLoadAnalyzer:
    """
    Estimates operator cognitive load from five weighted signals and classifies
    the result into an OverloadState.

    Total load formula
    ------------------
    total = sum(signal.weight * signal.value  for  signal in signals)

    Usage::

        analyzer = CognitiveLoadAnalyzer()
        report = analyzer.analyze(
            operator_id="op-42",
            active_ambiguity_count=3,
            unresolved_incidents=6,
            alert_density=0.7,
            explanation_complexity=0.5,
            contradictory_signals=2,
        )
    """

    # Signal configuration: (weight, saturation_divisor or None if pre-normalised)
    _SIGNAL_CONFIG: list[tuple[str, float, float | None]] = [
        # (name,                  weight, saturation_value or None)
        ("active_ambiguity", 0.25, 5.0),
        ("unresolved_pressure", 0.20, 10.0),
        ("alert_density", 0.20, None),  # already 0.0–1.0
        ("explanation_complexity", 0.20, None),  # already 0.0–1.0
        ("contradictory_signals", 0.15, 5.0),
    ]

    def analyze(
        self,
        operator_id: str,
        active_ambiguity_count: int,
        unresolved_incidents: int,
        alert_density: float,
        explanation_complexity: float,
        contradictory_signals: int,
    ) -> CognitiveLoadReport:
        """
        Compute a CognitiveLoadReport for the given operator.

        Parameters
        ----------
        operator_id:
            Unique identifier for the operator being assessed.
        active_ambiguity_count:
            Number of currently active incidents with an ambiguous root cause.
            Saturates at 5 (= full load for this signal).
        unresolved_incidents:
            Total number of incidents assigned to this operator that are still
            open / unresolved.  Saturates at 10.
        alert_density:
            Current alert rate normalised to [0.0, 1.0] by the caller.
        explanation_complexity:
            Complexity of the most recent AI explanation, normalised to
            [0.0, 1.0] (e.g. derived from token count or readability score).
        contradictory_signals:
            Number of pairs of mutually contradictory diagnostic signals
            present in the current incident context.  Saturates at 5.
        """
        # Map parameter names to raw values
        raw_values: dict[str, float] = {
            "active_ambiguity": float(active_ambiguity_count),
            "unresolved_pressure": float(unresolved_incidents),
            "alert_density": alert_density,
            "explanation_complexity": explanation_complexity,
            "contradictory_signals": float(contradictory_signals),
        }

        # Normalise and build signal list
        signals: list[CognitiveLoadSignal] = []
        for name, weight, saturation in self._SIGNAL_CONFIG:
            raw = raw_values[name]
            if saturation is not None:
                value = min(raw / saturation, 1.0)
            else:
                value = min(raw, 1.0)
            contribution = round(weight * value, 6)
            signals.append(
                CognitiveLoadSignal(
                    signal_name=name,
                    value=round(value, 6),
                    weight=weight,
                    contribution=contribution,
                )
            )

        total = round(min(sum(s.contribution for s in signals), 1.0), 6)
        state = self._classify_state(total)
        suppression_active = state in (OverloadState.OVERLOADED, OverloadState.SATURATED)

        return CognitiveLoadReport(
            operator_id=operator_id,
            signals=signals,
            total_cognitive_load=total,
            state=state,
            active_ambiguity_count=active_ambiguity_count,
            unresolved_count=unresolved_incidents,
            alert_density=alert_density,
            explanation_complexity=explanation_complexity,
            contradictory_signal_count=contradictory_signals,
            recommendation_suppression_active=suppression_active,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_state(total: float) -> OverloadState:
        """
        Map total cognitive load to an OverloadState.

        Thresholds
        ----------
        < 0.30  → NORMAL
        < 0.55  → ELEVATED
        < 0.80  → OVERLOADED
        >= 0.80 → SATURATED
        """
        if total < 0.30:
            return OverloadState.NORMAL
        if total < 0.55:
            return OverloadState.ELEVATED
        if total < 0.80:
            return OverloadState.OVERLOADED
        return OverloadState.SATURATED
