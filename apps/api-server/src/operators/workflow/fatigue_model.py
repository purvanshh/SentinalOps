"""
Fatigue Model for SentinelOps Phase 49.

Models operator cognitive fatigue arising from sustained incident response
activity. Five orthogonal signals are combined into a composite fatigue score
that determines escalation suppression and recommended interventions:

  - escalation_density          — escalations per hour (>10/hr = fully fatigued)
  - override_burden             — overrides issued per incident (0.0–1.0)
  - ambiguity_frequency         — fraction of incidents with ambiguous root cause
  - alert_noise_ratio           — false positives as a fraction of total alerts
  - unresolved_incident_pressure — fraction of open incidents still unresolved

FatigueModel.assess() returns a FatigueAssessment that flags when
non-critical notifications should be suppressed to protect the operator.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FatigueLevel(Enum):
    """Qualitative fatigue classification derived from the composite score."""

    NOMINAL = "NOMINAL"  # composite < 0.25
    ELEVATED = "ELEVATED"  # 0.25 <= composite < 0.50
    HIGH = "HIGH"  # 0.50 <= composite < 0.75
    CRITICAL = "CRITICAL"  # composite >= 0.75


@dataclass
class FatigueSignals:
    """Raw fatigue signal values collected from an operator's recent session."""

    escalation_density: float  # escalations per hour (0.0+)
    override_burden: float  # overrides per incident, normalised 0.0–1.0
    ambiguity_frequency: float  # fraction of incidents with ambiguous root cause (0.0–1.0)
    alert_noise_ratio: float  # false positives / total alerts (0.0–1.0)
    unresolved_incident_pressure: float  # fraction of incidents still open (0.0–1.0)


@dataclass
class FatigueAssessment:
    """Full fatigue assessment produced by FatigueModel.assess()."""

    operator_id: str
    signals: FatigueSignals
    composite_fatigue_score: float  # 0.0–1.0
    fatigue_level: FatigueLevel
    dominant_signal: str  # name of the highest-contributing signal
    suppress_non_critical: bool  # True when fatigue_level is HIGH or CRITICAL


class FatigueModel:
    """
    Estimates operator fatigue from five weighted signals and classifies
    the result into a FatigueLevel.

    Composite formula
    -----------------
    composite = (
        0.25 * min(escalation_density / 10.0, 1.0)
      + 0.20 * override_burden
      + 0.20 * ambiguity_frequency
      + 0.20 * alert_noise_ratio
      + 0.15 * unresolved_incident_pressure
    )

    Usage::

        model = FatigueModel()
        assessment = model.assess(
            operator_id="op-42",
            escalation_density=8.0,
            override_burden=0.6,
            ambiguity_frequency=0.5,
            alert_noise_ratio=0.3,
            unresolved_incident_pressure=0.4,
        )
    """

    # Weights must sum to 1.0
    _WEIGHTS: dict[str, float] = {
        "escalation_density": 0.25,
        "override_burden": 0.20,
        "ambiguity_frequency": 0.20,
        "alert_noise_ratio": 0.20,
        "unresolved_incident_pressure": 0.15,
    }

    # escalation_density saturation point (10 escalations/hr => fully fatigued)
    _ESCALATION_SATURATION: float = 10.0

    def assess(
        self,
        operator_id: str,
        escalation_density: float,
        override_burden: float,
        ambiguity_frequency: float,
        alert_noise_ratio: float,
        unresolved_incident_pressure: float,
    ) -> FatigueAssessment:
        """
        Compute a FatigueAssessment for the given operator signal values.

        Parameters
        ----------
        operator_id:
            Unique identifier for the operator being assessed.
        escalation_density:
            Number of escalations per hour in the current session (0.0+).
        override_burden:
            Normalised override rate per incident (0.0–1.0).
        ambiguity_frequency:
            Fraction of incidents that had an ambiguous root cause (0.0–1.0).
        alert_noise_ratio:
            Fraction of total alerts that were false positives (0.0–1.0).
        unresolved_incident_pressure:
            Fraction of all assigned incidents still unresolved (0.0–1.0).
        """
        # --- Normalise signals to [0.0, 1.0] ----------------------------
        normalised: dict[str, float] = {
            "escalation_density": min(escalation_density / self._ESCALATION_SATURATION, 1.0),
            "override_burden": min(override_burden, 1.0),
            "ambiguity_frequency": min(ambiguity_frequency, 1.0),
            "alert_noise_ratio": min(alert_noise_ratio, 1.0),
            "unresolved_incident_pressure": min(unresolved_incident_pressure, 1.0),
        }

        # --- Weighted contributions -------------------------------------
        contributions: dict[str, float] = {
            name: self._WEIGHTS[name] * normalised[name] for name in self._WEIGHTS
        }

        composite = round(sum(contributions.values()), 6)
        composite = min(composite, 1.0)  # clamp floating-point edge cases

        # --- Classify fatigue level ------------------------------------
        fatigue_level = self._classify_level(composite)

        # --- Identify dominant signal (highest weighted contribution) --
        dominant_signal = max(contributions, key=lambda k: contributions[k])

        # --- Suppression flag ------------------------------------------
        suppress_non_critical = fatigue_level in (FatigueLevel.HIGH, FatigueLevel.CRITICAL)

        signals = FatigueSignals(
            escalation_density=escalation_density,
            override_burden=override_burden,
            ambiguity_frequency=ambiguity_frequency,
            alert_noise_ratio=alert_noise_ratio,
            unresolved_incident_pressure=unresolved_incident_pressure,
        )

        return FatigueAssessment(
            operator_id=operator_id,
            signals=signals,
            composite_fatigue_score=composite,
            fatigue_level=fatigue_level,
            dominant_signal=dominant_signal,
            suppress_non_critical=suppress_non_critical,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_level(composite: float) -> FatigueLevel:
        """
        Map composite score to a FatigueLevel.

        Thresholds
        ----------
        < 0.25  → NOMINAL
        < 0.50  → ELEVATED
        < 0.75  → HIGH
        >= 0.75 → CRITICAL
        """
        if composite < 0.25:
            return FatigueLevel.NOMINAL
        if composite < 0.50:
            return FatigueLevel.ELEVATED
        if composite < 0.75:
            return FatigueLevel.HIGH
        return FatigueLevel.CRITICAL
