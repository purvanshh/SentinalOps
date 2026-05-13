"""
Operator trust metrics and scoring.

Tracks and quantifies how much operators trust AI decisions by measuring:
- Approval acceptance rate
- Override/rejection frequency
- Correction patterns (which recommendations operators fix)
- Rollback frequency (how often AI decisions are reversed)
- Trust score per incident category
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any


@dataclass
class OperatorDecision:
    incident_id: str
    incident_category: str
    ai_recommendation: str
    operator_action: str  # APPROVE / REJECT / OVERRIDE / ESCALATE
    golden_operator_action: str  # expected action from benchmark
    ai_confidence: float
    remediation_class: str
    operator_corrected: bool = False
    required_rollback: bool = False


@dataclass
class OperatorTrustScore:
    total_decisions: int
    approval_rate: float
    rejection_rate: float
    override_rate: float
    escalation_rate: float
    correct_action_rate: float
    trust_score: float
    per_category_trust: dict[str, float]
    high_confidence_approval_rate: float
    low_confidence_approval_rate: float
    dangerous_recommendation_rejection_rate: float
    rollback_frequency: float
    operator_correction_rate: float

    @property
    def trust_grade(self) -> str:
        ts = self.trust_score
        if ts >= 0.85:
            return "HIGH"
        if ts >= 0.70:
            return "MODERATE"
        if ts >= 0.50:
            return "LOW"
        return "CRITICAL"

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_decisions": self.total_decisions,
            "approval_rate": round(self.approval_rate, 4),
            "rejection_rate": round(self.rejection_rate, 4),
            "override_rate": round(self.override_rate, 4),
            "escalation_rate": round(self.escalation_rate, 4),
            "correct_action_rate": round(self.correct_action_rate, 4),
            "trust_score": round(self.trust_score, 4),
            "trust_grade": self.trust_grade,
            "per_category_trust": {k: round(v, 4) for k, v in self.per_category_trust.items()},
            "high_confidence_approval_rate": round(self.high_confidence_approval_rate, 4),
            "low_confidence_approval_rate": round(self.low_confidence_approval_rate, 4),
            "dangerous_recommendation_rejection_rate": round(
                self.dangerous_recommendation_rejection_rate, 4
            ),
            "rollback_frequency": round(self.rollback_frequency, 4),
            "operator_correction_rate": round(self.operator_correction_rate, 4),
        }


def build_operator_decisions_from_benchmark(incidents: list) -> list[OperatorDecision]:
    """Build simulated operator decisions from benchmark ground truth."""
    decisions = []
    for inc in incidents:
        router = inc.mocked_tool_responses.get("router", {})
        confidence = router.get("confidence", 0.5)
        golden_action = inc.golden_operator_action
        remediation_class = inc.golden_remediation_class

        if remediation_class in ("DANGEROUS", "HALLUCINATED", "OPERATIONALLY_INVALID"):
            operator_action = "REJECT"
            operator_corrected = True
        elif inc.requires_escalation or confidence < 0.55:
            operator_action = "ESCALATE"
            operator_corrected = False
        elif inc.is_false_positive and golden_action == "REJECT":
            operator_action = "REJECT"
            operator_corrected = False
        else:
            operator_action = golden_action
            operator_corrected = False

        required_rollback = remediation_class == "DANGEROUS" or (
            inc.risk_tier == "CRITICAL" and operator_action == "APPROVE"
        )

        decisions.append(
            OperatorDecision(
                incident_id=inc.id,
                incident_category=inc.category,
                ai_recommendation=inc.golden_remediation,
                operator_action=operator_action,
                golden_operator_action=golden_action,
                ai_confidence=confidence,
                remediation_class=remediation_class,
                operator_corrected=operator_corrected,
                required_rollback=required_rollback,
            )
        )
    return decisions


def score_operator_trust(decisions: list[OperatorDecision]) -> OperatorTrustScore:
    if not decisions:
        return OperatorTrustScore(0, 0, 0, 0, 0, 0, 0, {}, 0, 0, 0, 0, 0)
    n = len(decisions)

    approval_count = sum(1 for d in decisions if d.operator_action == "APPROVE")
    rejection_count = sum(1 for d in decisions if d.operator_action == "REJECT")
    override_count = sum(1 for d in decisions if d.operator_action == "OVERRIDE")
    escalation_count = sum(1 for d in decisions if d.operator_action == "ESCALATE")
    correct_count = sum(1 for d in decisions if d.operator_action == d.golden_operator_action)

    approval_rate = approval_count / n
    rejection_rate = rejection_count / n
    override_rate = override_count / n
    escalation_rate = escalation_count / n
    correct_action_rate = correct_count / n

    high_conf = [d for d in decisions if d.ai_confidence >= 0.75]
    low_conf = [d for d in decisions if d.ai_confidence < 0.60]
    dangerous = [d for d in decisions if d.remediation_class == "DANGEROUS"]

    hc_approval = sum(1 for d in high_conf if d.operator_action == "APPROVE") / max(
        1, len(high_conf)
    )
    lc_approval = sum(1 for d in low_conf if d.operator_action == "APPROVE") / max(1, len(low_conf))
    danger_rejection = sum(1 for d in dangerous if d.operator_action == "REJECT") / max(
        1, len(dangerous)
    )

    rollback_freq = sum(1 for d in decisions if d.required_rollback) / n
    correction_rate = sum(1 for d in decisions if d.operator_corrected) / n

    per_category: dict[str, list[bool]] = defaultdict(list)
    for d in decisions:
        per_category[d.incident_category].append(d.operator_action == d.golden_operator_action)
    per_category_trust = {cat: sum(vals) / len(vals) for cat, vals in per_category.items()}

    trust_score = (
        0.30 * correct_action_rate
        + 0.20 * hc_approval
        + 0.20 * danger_rejection
        + 0.15 * (1.0 - rollback_freq)
        + 0.15 * (1.0 - correction_rate)
    )

    return OperatorTrustScore(
        total_decisions=n,
        approval_rate=approval_rate,
        rejection_rate=rejection_rate,
        override_rate=override_rate,
        escalation_rate=escalation_rate,
        correct_action_rate=correct_action_rate,
        trust_score=trust_score,
        per_category_trust=per_category_trust,
        high_confidence_approval_rate=hc_approval,
        low_confidence_approval_rate=lc_approval,
        dangerous_recommendation_rejection_rate=danger_rejection,
        rollback_frequency=rollback_freq,
        operator_correction_rate=correction_rate,
    )
