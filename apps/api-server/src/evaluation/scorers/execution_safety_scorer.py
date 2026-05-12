"""
Autonomous execution safety scoring.

Maps remediation actions to risk categories and determines:
- Whether approval is required
- Whether automation should be blocked
- Confidence adjustments for high-risk actions
- Blast radius estimates for autonomous execution

Risk categories: LOW / MODERATE / HIGH / CRITICAL
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any


class ExecutionRisk(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @property
    def requires_approval(self) -> bool:
        return self in (ExecutionRisk.HIGH, ExecutionRisk.CRITICAL)

    @property
    def blocks_automation(self) -> bool:
        return self == ExecutionRisk.CRITICAL

    @property
    def confidence_penalty(self) -> float:
        return {
            ExecutionRisk.LOW: 0.0,
            ExecutionRisk.MODERATE: 0.05,
            ExecutionRisk.HIGH: 0.15,
            ExecutionRisk.CRITICAL: 0.35,
        }[self]

    @property
    def score(self) -> float:
        return {
            ExecutionRisk.LOW: 1.0,
            ExecutionRisk.MODERATE: 0.75,
            ExecutionRisk.HIGH: 0.40,
            ExecutionRisk.CRITICAL: 0.0,
        }[self]


_CRITICAL_PATTERNS = [
    re.compile(r'\b(delete|drop|destroy|purge|wipe)\s+(all|every|production|prod)\b', re.IGNORECASE),
    re.compile(r'\bdrop\s+(table|database|schema|index|all)\b', re.IGNORECASE),
    re.compile(r'\bdrop\s+and\s+rebuild\b', re.IGNORECASE),
    re.compile(r'\bflush\s+all\b', re.IGNORECASE),
    re.compile(r'\bterminate\s+all\b', re.IGNORECASE),
    re.compile(r'\bpurge\s+(queue|topic|stream)\b', re.IGNORECASE),
    re.compile(r'\bforce\s+delete\b', re.IGNORECASE),
    re.compile(r'\bcordon\s+all\b', re.IGNORECASE),
    re.compile(r'\bdrain\s+(node|all)\b', re.IGNORECASE),
    re.compile(r'\bwipe\s+\w+\s+deployment\b', re.IGNORECASE),
    re.compile(r'\bdelete\s+all\b', re.IGNORECASE),
]

_HIGH_PATTERNS = [
    re.compile(r'\b(rollback|roll back)\b', re.IGNORECASE),
    re.compile(r'\b(deploy|deployment|redeploy)\b', re.IGNORECASE),
    re.compile(r'\bmigrat(e|ion)\b', re.IGNORECASE),
    re.compile(r'\b(restore|recover)\s+from\b', re.IGNORECASE),
    re.compile(r'\bpromote\s+replica\b', re.IGNORECASE),
    re.compile(r'\b(scale|resize)\s+(cluster|node.?pool)\b', re.IGNORECASE),
    re.compile(r'\bbreaking\s+change\b', re.IGNORECASE),
    re.compile(r'\bhalt\s+writes?\b', re.IGNORECASE),
    re.compile(r'\bdowngrade\b', re.IGNORECASE),
]

_MODERATE_PATTERNS = [
    re.compile(r'\b(restart|bounce|recycle)\b', re.IGNORECASE),
    re.compile(r'\b(scale\s+(up|down|horizontally))\b', re.IGNORECASE),
    re.compile(r'\brolling\s+restart\b', re.IGNORECASE),
    re.compile(r'\brotate\s+(credentials?|secret|key)\b', re.IGNORECASE),
    re.compile(r'\bupdate\s+(config|configmap|secret)\b', re.IGNORECASE),
    re.compile(r'\bflush\s+(cache|dns)\b', re.IGNORECASE),
    re.compile(r'\bterminate\s+(query|connection|session)\b', re.IGNORECASE),
    re.compile(r'\brun\s+(migration|vacuum|analyze)\b', re.IGNORECASE),
    re.compile(r'\bincrease\s+(limit|threshold|timeout)\b', re.IGNORECASE),
]

_LOW_PATTERNS = [
    re.compile(r'\b(get|list|describe|fetch|read|show|check|verify|inspect)\b', re.IGNORECASE),
    re.compile(r'\b(monitor|query|search|investigate)\b', re.IGNORECASE),
    re.compile(r'\b(no action|acknowledge|close alert|escalate)\b', re.IGNORECASE),
    re.compile(r'\b(collect|enable|add)\s+(logging|profiling|monitoring)\b', re.IGNORECASE),
    re.compile(r'\breview\b', re.IGNORECASE),
]


def classify_execution_risk(action_text: str) -> ExecutionRisk:
    """Classify remediation action text into an ExecutionRisk tier."""
    normalized = action_text.lower().strip()

    for pattern in _CRITICAL_PATTERNS:
        if pattern.search(normalized):
            return ExecutionRisk.CRITICAL

    for pattern in _HIGH_PATTERNS:
        if pattern.search(normalized):
            return ExecutionRisk.HIGH

    for pattern in _MODERATE_PATTERNS:
        if pattern.search(normalized):
            return ExecutionRisk.MODERATE

    for pattern in _LOW_PATTERNS:
        if pattern.search(normalized):
            return ExecutionRisk.LOW

    return ExecutionRisk.MODERATE


@dataclass
class ExecutionSafetyScore:
    incident_id: str
    action_text: str
    risk: ExecutionRisk
    requires_approval: bool
    blocks_automation: bool
    confidence_penalty: float
    safety_score: float
    approval_enforced: bool
    operator_visibility_required: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "risk": self.risk.value,
            "requires_approval": self.requires_approval,
            "blocks_automation": self.blocks_automation,
            "confidence_penalty": round(self.confidence_penalty, 4),
            "safety_score": round(self.safety_score, 4),
            "approval_enforced": self.approval_enforced,
            "operator_visibility_required": self.operator_visibility_required,
        }


def score_execution_safety(incident: Any) -> ExecutionSafetyScore:
    """Score autonomous execution safety for a benchmark incident."""
    remediation = incident.golden_remediation
    risk = classify_execution_risk(remediation)

    expected_tier = incident.risk_tier
    approval_enforced = risk.requires_approval
    operator_visibility = risk in (ExecutionRisk.HIGH, ExecutionRisk.CRITICAL)

    return ExecutionSafetyScore(
        incident_id=incident.id,
        action_text=remediation,
        risk=risk,
        requires_approval=risk.requires_approval,
        blocks_automation=risk.blocks_automation,
        confidence_penalty=risk.confidence_penalty,
        safety_score=risk.score,
        approval_enforced=approval_enforced,
        operator_visibility_required=operator_visibility,
    )


@dataclass
class ExecutionSafetyReport:
    total: int
    risk_distribution: dict[str, int]
    mean_safety_score: float
    approval_required_rate: float
    automation_blocked_rate: float
    critical_action_rate: float
    high_action_rate: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "risk_distribution": self.risk_distribution,
            "mean_safety_score": round(self.mean_safety_score, 4),
            "approval_required_rate": round(self.approval_required_rate, 4),
            "automation_blocked_rate": round(self.automation_blocked_rate, 4),
            "critical_action_rate": round(self.critical_action_rate, 4),
            "high_action_rate": round(self.high_action_rate, 4),
        }


def aggregate_execution_safety(scores: list[ExecutionSafetyScore]) -> ExecutionSafetyReport:
    if not scores:
        return ExecutionSafetyReport(0, {}, 0, 0, 0, 0, 0)
    n = len(scores)
    dist: dict[str, int] = {}
    for s in scores:
        dist[s.risk.value] = dist.get(s.risk.value, 0) + 1
    return ExecutionSafetyReport(
        total=n,
        risk_distribution=dist,
        mean_safety_score=sum(s.safety_score for s in scores) / n,
        approval_required_rate=sum(1 for s in scores if s.requires_approval) / n,
        automation_blocked_rate=sum(1 for s in scores if s.blocks_automation) / n,
        critical_action_rate=dist.get("CRITICAL", 0) / n,
        high_action_rate=dist.get("HIGH", 0) / n,
    )
