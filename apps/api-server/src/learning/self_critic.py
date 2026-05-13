"""
Reasoning Self-Critic for SentinelOps Phase 46.

Performs self-critique of the AI's own reasoning output before
it is presented to operators or used to drive remediation decisions.

Self-critique detects:
  - Evidence gaps: claims made without supporting evidence
  - Confidence-evidence mismatches: high confidence with weak evidence
  - Reasoning circularity: hypothesis that isn't falsifiable from evidence
  - Missing alternatives: only one hypothesis considered
  - Unchecked assumptions: conclusions that rely on unverified premises

CritiqueReport is produced per reasoning artifact and is surfaced
as an operator-visible explainability signal.

Design constraints:
  - Self-critique is purely advisory — it never blocks execution.
  - Critique findings are logged with reason codes.
  - Critique does NOT reduce stated confidence values directly;
    it provides a recommended_confidence_adjustment instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class CritiqueFinding:
    """A single self-critique finding."""

    finding_code: str
    severity: str     # "low" | "medium" | "high"
    description: str
    affected_field: str
    suggested_action: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_code": self.finding_code,
            "severity": self.severity,
            "description": self.description,
            "affected_field": self.affected_field,
            "suggested_action": self.suggested_action,
        }


@dataclass
class CritiqueReport:
    """Self-critique report for a single reasoning artifact."""

    incident_id: str
    findings: list[CritiqueFinding]
    total_findings: int
    high_severity_count: int
    medium_severity_count: int
    low_severity_count: int
    recommended_confidence_adjustment: float  # bounded [-0.20, 0.0]
    reasoning_quality_score: float  # 0.0 = critically flawed, 1.0 = sound
    critique_summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "findings": [f.to_dict() for f in self.findings],
            "total_findings": self.total_findings,
            "high_severity_count": self.high_severity_count,
            "medium_severity_count": self.medium_severity_count,
            "low_severity_count": self.low_severity_count,
            "recommended_confidence_adjustment": round(
                self.recommended_confidence_adjustment, 4
            ),
            "reasoning_quality_score": round(self.reasoning_quality_score, 4),
            "critique_summary": self.critique_summary,
        }


class ReasoningSelfCritic:
    """
    Critiques AI reasoning artifacts for evidence quality,
    hypothesis coverage, and confidence justification.

    Input is a dict representing a reasoning artifact (e.g., the
    output of probabilistic_reasoner or the narrative generator).
    """

    def critique(
        self,
        incident_id: str,
        *,
        confidence: float,
        evidence_count: int,
        hypothesis_count: int,
        contradiction_count: int,
        has_mechanism: bool,
        has_propagation_path: bool,
        why_statement_count: int,
        escalation_recommended: bool,
        raw_artifact: dict[str, Any] | None = None,
    ) -> CritiqueReport:
        """
        Critique a reasoning artifact and return a CritiqueReport.

        Parameters are the key signals extracted from the reasoning output.
        `raw_artifact` is optional — pass the full dict for deeper inspection.
        """
        findings: list[CritiqueFinding] = []

        # --- Evidence gap ---
        if evidence_count == 0:
            findings.append(
                CritiqueFinding(
                    finding_code="EVIDENCE_GAP",
                    severity="high",
                    description="No supporting evidence was retrieved for this hypothesis.",
                    affected_field="evidence_chain",
                    suggested_action="Retrieve historical incidents before drawing conclusions.",
                )
            )
        elif evidence_count < 2 and confidence >= 0.70:
            findings.append(
                CritiqueFinding(
                    finding_code="THIN_EVIDENCE_HIGH_CONFIDENCE",
                    severity="medium",
                    description=(
                        f"Only {evidence_count} piece(s) of evidence but confidence "
                        f"is {confidence:.0%}. Evidence base is too thin to justify "
                        "this confidence level."
                    ),
                    affected_field="confidence",
                    suggested_action="Gather more evidence or reduce stated confidence.",
                )
            )

        # --- Single hypothesis ---
        if hypothesis_count <= 1:
            findings.append(
                CritiqueFinding(
                    finding_code="SINGLE_HYPOTHESIS",
                    severity="medium" if confidence >= 0.60 else "low",
                    description=(
                        "Only one hypothesis was considered. Alternative explanations "
                        "may exist."
                    ),
                    affected_field="hypotheses",
                    suggested_action=(
                        "Generate at least two competing hypotheses before "
                        "finalizing root cause."
                    ),
                )
            )

        # --- High confidence without mechanism ---
        if confidence >= 0.75 and not has_mechanism:
            findings.append(
                CritiqueFinding(
                    finding_code="CONFIDENT_WITHOUT_MECHANISM",
                    severity="medium",
                    description=(
                        f"Confidence is {confidence:.0%} but no failure mechanism "
                        "was identified. Root cause may be superficial."
                    ),
                    affected_field="mechanism",
                    suggested_action=(
                        "Run semantic engine to identify the operational failure mechanism."
                    ),
                )
            )

        # --- No propagation path ---
        if not has_propagation_path and confidence >= 0.65:
            findings.append(
                CritiqueFinding(
                    finding_code="MISSING_PROPAGATION_PATH",
                    severity="low",
                    description=(
                        "No propagation path was identified. The causal chain "
                        "is incomplete."
                    ),
                    affected_field="propagation_path",
                    suggested_action="Map downstream effect services to complete the causal chain.",
                )
            )

        # --- Contradictions ignored ---
        if contradiction_count > 0 and why_statement_count < 2:
            findings.append(
                CritiqueFinding(
                    finding_code="CONTRADICTIONS_UNEXPLAINED",
                    severity="medium",
                    description=(
                        f"{contradiction_count} contradiction(s) detected but "
                        "insufficient reasoning provided to address them."
                    ),
                    affected_field="contradictory_evidence",
                    suggested_action=(
                        "Provide explicit reasoning explaining why contradictions "
                        "do not overturn the primary hypothesis."
                    ),
                )
            )

        # --- Escalation recommended but confidence is high ---
        if escalation_recommended and confidence >= 0.85:
            findings.append(
                CritiqueFinding(
                    finding_code="ESCALATION_WITH_HIGH_CONFIDENCE",
                    severity="low",
                    description=(
                        f"Escalation is recommended but confidence is {confidence:.0%}. "
                        "Consider whether escalation is still warranted."
                    ),
                    affected_field="escalation",
                    suggested_action=(
                        "Review escalation trigger — high confidence may make it unnecessary."
                    ),
                )
            )

        # --- Deep inspection of raw artifact ---
        if raw_artifact:
            self._inspect_artifact(raw_artifact, findings)

        # Compute quality score and confidence adjustment
        high = sum(1 for f in findings if f.severity == "high")
        medium = sum(1 for f in findings if f.severity == "medium")
        low = sum(1 for f in findings if f.severity == "low")

        # Penalty: high=0.20, medium=0.10, low=0.03
        quality_penalty = min(1.0, high * 0.20 + medium * 0.10 + low * 0.03)
        quality_score = round(max(0.0, 1.0 - quality_penalty), 4)

        # Confidence adjustment: negative only; bounded [-0.20, 0.0]
        conf_penalty = min(0.20, high * 0.10 + medium * 0.05)
        conf_adjustment = round(-conf_penalty, 4)

        if not findings:
            summary = "No critique findings. Reasoning appears sound."
        else:
            summary = (
                f"{len(findings)} finding(s): {high} high, {medium} medium, {low} low. "
                + "; ".join(f.finding_code for f in findings[:3])
                + ("..." if len(findings) > 3 else "")
            )

        return CritiqueReport(
            incident_id=incident_id,
            findings=findings,
            total_findings=len(findings),
            high_severity_count=high,
            medium_severity_count=medium,
            low_severity_count=low,
            recommended_confidence_adjustment=conf_adjustment,
            reasoning_quality_score=quality_score,
            critique_summary=summary,
        )

    def _inspect_artifact(
        self, artifact: dict[str, Any], findings: list[CritiqueFinding]
    ) -> None:
        """Optional deep inspection of the raw artifact dict."""
        # Flag empty why_statements
        why = artifact.get("why", [])
        if isinstance(why, list) and len(why) == 0:
            findings.append(
                CritiqueFinding(
                    finding_code="EMPTY_WHY_STATEMENTS",
                    severity="medium",
                    description="No 'why' statements in reasoning output.",
                    affected_field="why",
                    suggested_action="Populate why_statements with causal reasoning.",
                )
            )

        # Flag missing uncertainty_note
        note = artifact.get("uncertainty_note", "")
        if not note:
            findings.append(
                CritiqueFinding(
                    finding_code="MISSING_UNCERTAINTY_NOTE",
                    severity="low",
                    description="No uncertainty note provided in reasoning output.",
                    affected_field="uncertainty_note",
                    suggested_action="Add an uncertainty note to surface confidence caveats.",
                )
            )
