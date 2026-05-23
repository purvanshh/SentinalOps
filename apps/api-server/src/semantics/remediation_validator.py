"""
Semantic Remediation Validator for SentinelOps Phase 45.

Validates whether proposed remediation actions are semantically aligned
with the inferred failure mechanism. The core insight:

  Scaling frontend replicas does NOT fix database lock contention.
  Flushing cache does NOT fix thread pool saturation.
  Adding a database index does NOT fix a retry storm.

These are mechanism-remediation mismatches that a purely heuristic
remediation planner cannot detect. This module makes such mismatches explicit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from semantics.ontology import FailureMechanismOntology
from semantics.semantic_engine import MechanismInference


@dataclass
class RemediationAlignmentIssue:
    action: str
    issue_type: str
    description: str
    severity: str


@dataclass
class RemediationValidation:
    """Result of semantic remediation validation."""

    mechanism_id: str | None
    mechanism_name: str | None
    overall_compatible: bool
    alignment_score: float
    issues: list[RemediationAlignmentIssue]
    compatible_actions: list[str]
    incompatible_actions: list[str]
    suggested_alternatives: list[str]
    validation_rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "mechanism_id": self.mechanism_id,
            "mechanism_name": self.mechanism_name,
            "overall_compatible": self.overall_compatible,
            "alignment_score": round(self.alignment_score, 4),
            "issue_count": len(self.issues),
            "issues": [
                {
                    "action": issue.action,
                    "issue_type": issue.issue_type,
                    "description": issue.description,
                    "severity": issue.severity,
                }
                for issue in self.issues
            ],
            "compatible_actions": self.compatible_actions,
            "incompatible_actions": self.incompatible_actions,
            "suggested_alternatives": self.suggested_alternatives,
            "validation_rationale": self.validation_rationale,
        }


# Canonical remediation action tokens for incompatibility detection
_REMEDIATION_ACTION_PATTERNS: dict[str, list[str]] = {
    "scale_frontend": [
        "scale frontend",
        "increase frontend replicas",
        "scale web",
        "add frontend pods",
        "scale api pods",
        "increase api replicas",
    ],
    "flush_cache": [
        "flush cache",
        "clear cache",
        "invalidate cache",
        "cache flush",
        "redis flush",
        "memcache flush",
    ],
    "add_database_index": [
        "add index",
        "create index",
        "database index",
        "add db index",
    ],
    "scale_database": [
        "scale database",
        "increase db",
        "add db replica",
        "scale postgres",
    ],
    "scale_consumers": [
        "scale consumer",
        "add consumer",
        "increase consumer",
        "consumer scale",
    ],
    "restart_load_balancer": [
        "restart load balancer",
        "restart nginx",
        "restart haproxy",
    ],
    "rollback_deployment": [
        "rollback",
        "revert deployment",
        "revert release",
        "rollback deploy",
    ],
    "increase_pool_size": [
        "increase pool size",
        "pool size",
        "connection pool limit",
    ],
}


def _detect_action_tokens(remediation_text: str) -> list[str]:
    lower = remediation_text.lower()
    matched: list[str] = []
    for action_id, patterns in _REMEDIATION_ACTION_PATTERNS.items():
        if any(pattern in lower for pattern in patterns):
            matched.append(action_id)
    return matched


class SemanticRemediationValidator:
    """
    Validates remediation plans against inferred failure mechanisms.

    Produces an alignment score and identifies actions that are
    incompatible with the operational failure mechanism.
    """

    def __init__(self, ontology: FailureMechanismOntology | None = None) -> None:
        self._ontology = ontology or FailureMechanismOntology()

    def validate(
        self,
        remediation_text: str,
        inference: MechanismInference | None,
    ) -> RemediationValidation:
        if inference is None or inference.primary is None:
            return RemediationValidation(
                mechanism_id=None,
                mechanism_name=None,
                overall_compatible=True,
                alignment_score=0.5,
                issues=[],
                compatible_actions=[],
                incompatible_actions=[],
                suggested_alternatives=[],
                validation_rationale=(
                    "No mechanism inferred; remediation compatibility cannot be assessed."
                ),
            )

        mechanism = inference.primary.mechanism
        compatible, incompatibility_reason = self._ontology.validate_remediation(
            remediation_text, mechanism.mechanism_id
        )

        # Detailed action-level analysis
        detected_actions = _detect_action_tokens(remediation_text)
        incompatible_actions: list[str] = []
        compatible_actions: list[str] = []
        issues: list[RemediationAlignmentIssue] = []

        for action_id in detected_actions:
            if action_id in mechanism.incompatible_remediations:
                incompatible_actions.append(action_id)
                issues.append(
                    RemediationAlignmentIssue(
                        action=action_id,
                        issue_type="mechanism_mismatch",
                        description=(
                            f"'{action_id.replace('_', ' ')}' does not address "
                            f"'{mechanism.name}'. "
                            f"{incompatibility_reason or 'This action targets a different part of the system.'}"  # noqa: E501
                        ),
                        severity="HIGH",
                    )
                )
            elif any(action_id in rem for rem in mechanism.plausible_remediations):
                compatible_actions.append(action_id)

        # Check if at least one plausible remediation is present
        has_plausible = any(
            any(pat in remediation_text.lower() for pat in patterns)
            for action_id, patterns in _REMEDIATION_ACTION_PATTERNS.items()
            if action_id in mechanism.plausible_remediations
        )

        if not has_plausible and remediation_text.strip():
            issues.append(
                RemediationAlignmentIssue(
                    action="remediation_plan",
                    issue_type="missing_mechanism_aligned_action",
                    description=(
                        f"No action in the remediation plan directly addresses "
                        f"'{mechanism.name}'. "
                        f"Expected actions: {', '.join(list(mechanism.plausible_remediations)[:3])}."  # noqa: E501
                    ),
                    severity="MEDIUM",
                )
            )

        # Alignment score
        if not remediation_text.strip():
            alignment_score = 0.0
        elif incompatible_actions and not compatible_actions:
            alignment_score = 0.1
        elif incompatible_actions:
            alignment_score = 0.4
        elif has_plausible:
            alignment_score = 0.85
        else:
            alignment_score = 0.35

        overall_compatible = len(incompatible_actions) == 0 and has_plausible

        # Suggested alternatives from mechanism
        suggested = list(mechanism.plausible_remediations[:3])

        rationale = (
            f"Remediation evaluated against mechanism '{mechanism.name}'. "
            f"Incompatible actions: {incompatible_actions or 'none'}. "
            f"Mechanism-aligned actions present: {has_plausible}."
        )

        return RemediationValidation(
            mechanism_id=mechanism.mechanism_id,
            mechanism_name=mechanism.name,
            overall_compatible=overall_compatible,
            alignment_score=round(alignment_score, 4),
            issues=issues,
            compatible_actions=compatible_actions,
            incompatible_actions=incompatible_actions,
            suggested_alternatives=suggested,
            validation_rationale=rationale,
        )
