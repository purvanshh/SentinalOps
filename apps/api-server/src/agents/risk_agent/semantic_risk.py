"""
Semantic risk layer for SentinelOps Phase 45.

Enriches remediation risk assessments with:
  - mechanism-remediation alignment scores
  - semantic contradiction detection
  - mechanism-based compatibility flags

These checks run independently of execution history and catch cases where
a remediation action is historically successful but operationally wrong for
the current inferred failure mechanism.
"""

from __future__ import annotations

from typing import Any

from semantics.contradiction_detector import (
    SemanticContradictionDetector,
    SemanticContradictionReport,
)
from semantics.remediation_validator import RemediationValidation, SemanticRemediationValidator
from semantics.semantic_engine import MechanismInference, OperationalSemanticEngine


def build_mechanism_inference(
    evidence_items: list[dict[str, Any]],
    timed_events: list[Any],
    incident_type: str | None = None,
) -> MechanismInference:
    """Infer the operational failure mechanism from evidence."""
    engine = OperationalSemanticEngine()
    return engine.infer_mechanism(evidence_items, timed_events, incident_type=incident_type)


def validate_remediation_plan(
    remediation_text: str,
    inference: MechanismInference | None,
) -> RemediationValidation:
    """Validate a remediation plan against the inferred failure mechanism."""
    validator = SemanticRemediationValidator()
    return validator.validate(remediation_text, inference)


def detect_semantic_contradictions(
    evidence_items: list[dict[str, Any]],
    timed_events: list[Any],
    inference: MechanismInference | None,
    remediation_text: str = "",
) -> SemanticContradictionReport:
    """Detect semantic contradictions between evidence, mechanism, and remediation."""
    detector = SemanticContradictionDetector()
    return detector.detect(
        evidence_items=evidence_items,
        timed_events=timed_events,
        inference=inference,
        remediation_text=remediation_text,
    )


def enrich_remediation_risk(
    action: str,
    risk_result: dict[str, Any],
    inference: MechanismInference | None,
) -> dict[str, Any]:
    """
    Enrich a single remediation action's risk result with semantic alignment.

    Adds:
      - semantic_alignment_score: float [0,1]
      - semantic_compatible: bool
      - semantic_issues: list of issue descriptions
    """
    validation = validate_remediation_plan(action, inference)
    enriched = dict(risk_result)
    enriched["semantic_alignment_score"] = validation.alignment_score
    enriched["semantic_compatible"] = validation.overall_compatible
    enriched["semantic_issues"] = [issue.description for issue in validation.issues]
    # If semantically incompatible, penalize the risk score upward
    if not validation.overall_compatible and validation.issues:
        penalty = min(0.30, 0.10 * len(validation.issues))
        enriched["risk_score"] = round(min(1.0, enriched.get("risk_score", 0.5) + penalty), 4)
        if enriched.get("recommendation") == "safe to proceed":
            enriched["recommendation"] = "review — semantic mismatch with inferred mechanism"
    return enriched
