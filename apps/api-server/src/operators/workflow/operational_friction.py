"""
Operational Friction Analysis for SentinelOps Phase 49.

Models the cumulative cognitive and operational friction an operator faces
when executing a remediation recommendation under real-world conditions:

  - LOW_CONFIDENCE          — AI confidence below threshold increases hesitation
  - HIGH_FATIGUE            — operator fatigue degrades execution quality
  - CONCURRENT_INCIDENTS    — competing incidents dilute operator attention
  - MISSING_ROLLBACK        — no rollback path raises the stakes of execution
  - LENGTHY_RECOMMENDATION  — overly long recommendations slow response time

OperationalFrictionAnalyzer.analyze() returns an OperationalFrictionReport
per incident that signals when execution should be deferred or escalated.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FrictionFactor:
    """A single operational friction factor contributing to total friction."""

    factor_name: str  # short identifier, e.g. "LOW_CONFIDENCE"
    friction_cost: float  # 0.0–1.0
    description: str


@dataclass
class OperationalFrictionReport:
    """Per-incident operational friction report for a remediation recommendation."""

    incident_id: str
    factors: list[FrictionFactor]
    total_friction: float  # sum of friction_costs capped at 1.0
    execution_difficulty: str  # "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
    recommended_deferral: bool  # True if total_friction > 0.7


class OperationalFrictionAnalyzer:
    """
    Estimates the operational friction an operator will experience when
    executing a given remediation recommendation.

    Usage::

        analyzer = OperationalFrictionAnalyzer()
        report = analyzer.analyze(
            incident_id="inc-001",
            recommendation="kubectl rollout restart deployment/api",
            operator_fatigue=0.80,
            concurrent_incidents=2,
            confidence=0.45,
        )
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(
        self,
        incident_id: str,
        recommendation: str,
        operator_fatigue: float,
        concurrent_incidents: int,
        confidence: float,
    ) -> OperationalFrictionReport:
        """
        Compute an OperationalFrictionReport for the given recommendation.

        Parameters
        ----------
        incident_id:
            Unique identifier for the incident being analysed.
        recommendation:
            Full text of the AI-generated remediation recommendation.
        operator_fatigue:
            Current operator fatigue level (0.0 = fresh, 1.0 = exhausted).
        concurrent_incidents:
            Number of other active incidents the operator is managing in
            parallel (including this one counts as 1, so 0 means only this
            incident).
        confidence:
            AI model's stated confidence in the recommendation (0.0–1.0).
        """
        factors: list[FrictionFactor] = []
        rec_lower = recommendation.lower()

        # ---- Factor 1: Low confidence ------------------------------------
        if confidence < 0.50:
            factors.append(
                FrictionFactor(
                    factor_name="LOW_CONFIDENCE",
                    friction_cost=0.25,
                    description=(
                        f"AI confidence is {confidence:.2f}, below the 0.50 threshold. "
                        "Operators must perform additional validation before acting, "
                        "increasing cognitive load and time-to-action."
                    ),
                )
            )

        # ---- Factor 2: High operator fatigue -----------------------------
        if operator_fatigue > 0.70:
            factors.append(
                FrictionFactor(
                    factor_name="HIGH_FATIGUE",
                    friction_cost=0.20,
                    description=(
                        f"Operator fatigue is {operator_fatigue:.2f}, above the 0.70 "
                        "threshold. Fatigued operators are more prone to execution "
                        "errors and slower decision-making."
                    ),
                )
            )

        # ---- Factor 3: Concurrent incidents ------------------------------
        concurrent_cost = 0.10 * min(concurrent_incidents, 3)
        if concurrent_cost > 0.0:
            factors.append(
                FrictionFactor(
                    factor_name="CONCURRENT_INCIDENTS",
                    friction_cost=concurrent_cost,
                    description=(
                        f"Operator is managing {concurrent_incidents} concurrent "
                        f"incident(s). Attention is split, adding {concurrent_cost:.2f} "
                        "friction cost (0.10 per incident, capped at 3)."
                    ),
                )
            )

        # ---- Factor 4: Missing rollback ----------------------------------
        if "rollback" not in rec_lower:
            factors.append(
                FrictionFactor(
                    factor_name="MISSING_ROLLBACK",
                    friction_cost=0.15,
                    description=(
                        "The recommendation does not mention a rollback procedure. "
                        "Operators must improvise a recovery path if execution fails, "
                        "raising the effective risk of the action."
                    ),
                )
            )

        # ---- Factor 5: Lengthy recommendation ----------------------------
        if len(recommendation) > 500:
            factors.append(
                FrictionFactor(
                    factor_name="LENGTHY_RECOMMENDATION",
                    friction_cost=0.10,
                    description=(
                        f"Recommendation is {len(recommendation)} characters long "
                        "(> 500). Lengthy instructions slow comprehension and "
                        "increase the chance of skipping critical steps under pressure."
                    ),
                )
            )

        # ---- Aggregate ---------------------------------------------------
        total_friction = min(1.0, sum(f.friction_cost for f in factors))
        execution_difficulty = self._classify_difficulty(total_friction)
        recommended_deferral = total_friction > 0.70

        return OperationalFrictionReport(
            incident_id=incident_id,
            factors=factors,
            total_friction=round(total_friction, 4),
            execution_difficulty=execution_difficulty,
            recommended_deferral=recommended_deferral,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_difficulty(total_friction: float) -> str:
        """
        Map total friction to a qualitative execution difficulty label.

        Thresholds
        ----------
        < 0.25  → "LOW"
        < 0.50  → "MEDIUM"
        < 0.75  → "HIGH"
        ≥ 0.75  → "CRITICAL"
        """
        if total_friction < 0.25:
            return "LOW"
        if total_friction < 0.50:
            return "MEDIUM"
        if total_friction < 0.75:
            return "HIGH"
        return "CRITICAL"
