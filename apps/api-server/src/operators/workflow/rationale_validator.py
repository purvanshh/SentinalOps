"""
Rationale Validator for SentinelOps Phase 49.

Validates that an AI-generated incident rationale meets epistemic quality
standards before it is surfaced to operators or used to drive escalation.

Detected violation types:
  UNSUPPORTED_CERTAINTY   — high confidence without sufficient evidence
  MISSING_EVIDENCE_LINK   — causal assertion with no evidence references
  UNEXPLAINED_ESCALATION  — escalation mentioned but no reason given
  CONTRADICTORY_NARRATIVE — narrative contains mutually exclusive claims
  OVER_SPECIFIC_CLAIM     — low confidence paired with specific-sounding numbers

RationaleValidator.validate() returns a RationaleValidationResult that
captures all violations and a binary passed / failed outcome.

Design constraints:
  - Validation is purely advisory — it never blocks execution.
  - `passed` is True only when there are no high-severity violations.
  - Severity levels are: "low" | "medium" | "high".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class RationaleIssue(Enum):
    UNSUPPORTED_CERTAINTY = "UNSUPPORTED_CERTAINTY"
    MISSING_EVIDENCE_LINK = "MISSING_EVIDENCE_LINK"
    UNEXPLAINED_ESCALATION = "UNEXPLAINED_ESCALATION"
    CONTRADICTORY_NARRATIVE = "CONTRADICTORY_NARRATIVE"
    OVER_SPECIFIC_CLAIM = "OVER_SPECIFIC_CLAIM"
    VAGUE_ROOT_CAUSE = "VAGUE_ROOT_CAUSE"


@dataclass
class RationaleViolation:
    """A single detected violation within an incident rationale."""

    issue: RationaleIssue
    severity: str  # "low" | "medium" | "high"
    description: str
    affected_text: str


@dataclass
class RationaleValidationResult:
    """Aggregated validation result for one incident rationale."""

    incident_id: str
    violations: list[RationaleViolation]
    passed: bool
    total_violations: int
    high_severity_count: int


# ---------------------------------------------------------------------------
# Regex helpers (compiled once at module load)
# ---------------------------------------------------------------------------
_CAUSAL_RE = re.compile(r"\b(because|caused by)\b", re.IGNORECASE)
_ESCALATION_RE = re.compile(r"\bescalat", re.IGNORECASE)
_PERCENTAGE_RE = re.compile(r"\d+\.\d+%")

_CONTRADICTION_PAIRS: list[tuple[str, str]] = [
    ("resolved", "unresolved"),
    ("stable", "degrading"),
]


class RationaleValidator:
    """
    Validates an incident rationale against a set of epistemic quality rules.

    Usage::

        validator = RationaleValidator()
        result = validator.validate(
            incident_id="inc-001",
            narrative="The service degraded because of OOMKill. Escalate now.",
            confidence=0.92,
            evidence_refs=["ref-1"],
            escalation_reason=None,
        )
        print(result.passed)       # False — UNEXPLAINED_ESCALATION detected
    """

    def validate(
        self,
        incident_id: str,
        narrative: str,
        confidence: float,
        evidence_refs: list[str],
        escalation_reason: str | None,
    ) -> RationaleValidationResult:
        """
        Run all validation checks and return a RationaleValidationResult.

        Parameters
        ----------
        incident_id:
            Unique identifier for the incident being validated.
        narrative:
            Full text of the AI-generated rationale / narrative.
        confidence:
            Model's stated confidence in its root-cause assessment (0.0–1.0).
        evidence_refs:
            Evidence reference identifiers cited in support of the rationale.
        escalation_reason:
            Textual reason for escalation, or None if escalation was not
            recommended or the reason was omitted.
        """
        violations: list[RationaleViolation] = []
        narrative_lower = narrative.lower()

        # 1. UNSUPPORTED_CERTAINTY
        #    High confidence (> 0.85) but fewer than 2 evidence references.
        if confidence > 0.85 and len(evidence_refs) < 2:
            violations.append(
                RationaleViolation(
                    issue=RationaleIssue.UNSUPPORTED_CERTAINTY,
                    severity="high",
                    description=(
                        f"Confidence is {confidence:.0%} but only "
                        f"{len(evidence_refs)} evidence reference(s) provided. "
                        "At least 2 are required to justify this certainty level."
                    ),
                    affected_text=f"confidence={confidence:.2f}, evidence_refs={evidence_refs}",
                )
            )

        # 2. MISSING_EVIDENCE_LINK
        #    Narrative contains causal language but no evidence references at all.
        if _CAUSAL_RE.search(narrative) and len(evidence_refs) == 0:
            match = _CAUSAL_RE.search(narrative)
            affected = narrative[max(0, match.start() - 20) : match.end() + 40]
            violations.append(
                RationaleViolation(
                    issue=RationaleIssue.MISSING_EVIDENCE_LINK,
                    severity="high",
                    description=(
                        "Narrative makes a causal assertion ('because' / 'caused by') "
                        "but no evidence references were provided to support it."
                    ),
                    affected_text=affected.strip(),
                )
            )

        # 3. UNEXPLAINED_ESCALATION
        #    Narrative mentions escalation but no escalation_reason is given.
        if _ESCALATION_RE.search(narrative) and not (
            escalation_reason and escalation_reason.strip()
        ):
            match = _ESCALATION_RE.search(narrative)
            affected = narrative[max(0, match.start() - 10) : match.end() + 40]
            violations.append(
                RationaleViolation(
                    issue=RationaleIssue.UNEXPLAINED_ESCALATION,
                    severity="medium",
                    description=(
                        "Narrative references escalation but escalation_reason is "
                        "absent or empty. Operators need a clear escalation rationale."
                    ),
                    affected_text=affected.strip(),
                )
            )

        # 4. CONTRADICTORY_NARRATIVE
        #    Narrative contains mutually exclusive state descriptors.
        for term_a, term_b in _CONTRADICTION_PAIRS:
            if term_a in narrative_lower and term_b in narrative_lower:
                violations.append(
                    RationaleViolation(
                        issue=RationaleIssue.CONTRADICTORY_NARRATIVE,
                        severity="high",
                        description=(
                            f"Narrative simultaneously describes the system as "
                            f"'{term_a}' and '{term_b}', which are mutually exclusive states."
                        ),
                        affected_text=f"contains both '{term_a}' and '{term_b}'",
                    )
                )

        # 5. OVER_SPECIFIC_CLAIM
        #    Low confidence (< 0.40) but narrative contains specific percentage figures.
        if confidence < 0.40:
            percentage_matches = _PERCENTAGE_RE.findall(narrative)
            if percentage_matches:
                violations.append(
                    RationaleViolation(
                        issue=RationaleIssue.OVER_SPECIFIC_CLAIM,
                        severity="medium",
                        description=(
                            f"Confidence is only {confidence:.0%} yet the narrative "
                            f"contains specific percentage claim(s): "
                            f"{', '.join(percentage_matches)}. "
                            "Precise figures imply certainty that is not warranted."
                        ),
                        affected_text=", ".join(percentage_matches),
                    )
                )

        # Aggregate
        high_count = sum(1 for v in violations if v.severity == "high")
        passed = high_count == 0

        return RationaleValidationResult(
            incident_id=incident_id,
            violations=violations,
            passed=passed,
            total_violations=len(violations),
            high_severity_count=high_count,
        )
