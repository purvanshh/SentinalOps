"""
Escalation Fatigue Analysis for SentinelOps Phase 49.

Detects operator and system-level escalation fatigue by examining patterns in
escalation quality (spam rate), alert false-positive density, and recommendation
acceptance rates.  The goal is to identify when an escalation pipeline has
degraded into noise — causing operators to ignore or dismiss legitimate signals.

Key metrics
-----------
  escalation_spam_rate         — fraction of escalations that resolved without
                                 L3+ involvement (i.e. were unnecessary)
  alert_fatigue_risk           — True when >40 % of alerts are false positives
  recommendation_saturation    — True when >10 recommendations were issued
                                 without any operator acceptance

EscalationFatigueAnalyzer.analyze() returns an EscalationFatigueReport.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EscalationFatigueRisk(Enum):
    """Qualitative escalation fatigue risk level."""

    NONE = "NONE"  # healthy escalation behaviour
    LOW = "LOW"  # minor volume pressure
    MODERATE = "MODERATE"  # quality degradation beginning
    HIGH = "HIGH"  # significant fatigue; review escalation policy
    SPAM = "SPAM"  # pipeline has become noise; immediate intervention required


@dataclass
class EscalationFatigueReport:
    """Full escalation fatigue report produced by EscalationFatigueAnalyzer.analyze()."""

    operator_id: str
    escalation_count: int
    false_escalation_count: int  # escalations resolved without L3+ involvement
    chronic_uncertainty_escalations: int  # escalations triggered by uncertainty, not severity
    alert_fatigue_risk: bool  # True if FP rate > 40 %
    recommendation_saturation: bool  # True if unaccepted_recommendations > 10
    escalation_spam_rate: float  # false_escalation_count / max(escalation_count, 1)
    fatigue_risk: EscalationFatigueRisk


class EscalationFatigueAnalyzer:
    """
    Assesses escalation fatigue risk for an operator based on escalation quality,
    alert noise, and recommendation acceptance signals.

    Risk classification
    -------------------
    SPAM     spam_rate > 0.60  or  chronic_uncertainty_escalations > 5
    HIGH     spam_rate > 0.40  or  (alert_fatigue_risk and escalation_count > 10)
    MODERATE spam_rate > 0.20  or  chronic_uncertainty_escalations > 2
    LOW      escalation_count > 5
    NONE     otherwise

    Usage::

        analyzer = EscalationFatigueAnalyzer()
        report = analyzer.analyze(
            operator_id="op-42",
            escalation_count=15,
            false_escalation_count=10,
            chronic_uncertainty_escalations=3,
            total_alerts=50,
            false_positive_alerts=25,
            unaccepted_recommendations=12,
        )
    """

    def analyze(
        self,
        operator_id: str,
        escalation_count: int,
        false_escalation_count: int,
        chronic_uncertainty_escalations: int,
        total_alerts: int,
        false_positive_alerts: int,
        unaccepted_recommendations: int,
    ) -> EscalationFatigueReport:
        """
        Compute an EscalationFatigueReport for the given operator.

        Parameters
        ----------
        operator_id:
            Unique identifier for the operator being assessed.
        escalation_count:
            Total number of escalations raised by (or involving) this operator
            in the assessment window.
        false_escalation_count:
            Subset of escalations that resolved without any L3+ engineer
            involvement (i.e. were unnecessary or premature).
        chronic_uncertainty_escalations:
            Escalations that were triggered solely because the AI model was
            uncertain, not because the incident itself was severe.
        total_alerts:
            Total number of alerts received in the assessment window.
        false_positive_alerts:
            Subset of alerts that turned out to be false positives.
        unaccepted_recommendations:
            Number of AI recommendations issued in the window that the operator
            did not accept (dismissed or ignored).
        """
        # --- Derived metrics -------------------------------------------
        spam_rate = false_escalation_count / max(escalation_count, 1)
        fp_alert_rate = false_positive_alerts / max(total_alerts, 1)

        alert_fatigue_risk = fp_alert_rate > 0.40
        recommendation_saturation = unaccepted_recommendations > 10

        # --- Risk classification (evaluated highest → lowest) ----------
        fatigue_risk = self._classify_risk(
            spam_rate=spam_rate,
            chronic_uncertainty_escalations=chronic_uncertainty_escalations,
            alert_fatigue_risk=alert_fatigue_risk,
            escalation_count=escalation_count,
        )

        return EscalationFatigueReport(
            operator_id=operator_id,
            escalation_count=escalation_count,
            false_escalation_count=false_escalation_count,
            chronic_uncertainty_escalations=chronic_uncertainty_escalations,
            alert_fatigue_risk=alert_fatigue_risk,
            recommendation_saturation=recommendation_saturation,
            escalation_spam_rate=round(spam_rate, 6),
            fatigue_risk=fatigue_risk,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_risk(
        spam_rate: float,
        chronic_uncertainty_escalations: int,
        alert_fatigue_risk: bool,
        escalation_count: int,
    ) -> EscalationFatigueRisk:
        """
        Map derived metrics to an EscalationFatigueRisk level.

        Rules are evaluated from most-severe to least-severe; the first
        matching rule wins.
        """
        # SPAM — pipeline has become noise
        if spam_rate > 0.60 or chronic_uncertainty_escalations > 5:
            return EscalationFatigueRisk.SPAM

        # HIGH — significant fatigue
        if spam_rate > 0.40 or (alert_fatigue_risk and escalation_count > 10):
            return EscalationFatigueRisk.HIGH

        # MODERATE — quality degradation beginning
        if spam_rate > 0.20 or chronic_uncertainty_escalations > 2:
            return EscalationFatigueRisk.MODERATE

        # LOW — volume pressure only
        if escalation_count > 5:
            return EscalationFatigueRisk.LOW

        return EscalationFatigueRisk.NONE
