"""
Semantic Hallucination Checker for SentinelOps Phase 45.

Extends the rule-based hallucination detection (Phase 41) with
mechanism plausibility checks. The existing detector catches:
  - fabricated service names
  - dangerous remediation patterns
  - unsupported claims (keyword)
  - confidence-evidence mismatch

This module adds:
  - mechanism plausibility checks: does the claimed mechanism
    match the observable evidence?
  - infrastructure semantic consistency: does the causal chain
    make operational sense?
  - remediation plausibility scoring: is the remediation operationally
    sensible for the stated diagnosis?
  - confident nonsense detection: high confidence + low mechanism alignment
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from semantics.semantic_engine import MechanismInference


@dataclass
class SemanticHallucinationFinding:
    check_type: str
    description: str
    severity: str
    confidence_penalty: float
    evidence_fragment: str = ""


@dataclass
class SemanticHallucinationReport:
    findings: list[SemanticHallucinationFinding]
    mechanism_plausibility_score: float
    semantic_hallucination_detected: bool
    total_confidence_penalty: float
    risk_level: str
    plausibility_rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "semantic_hallucination_detected": self.semantic_hallucination_detected,
            "mechanism_plausibility_score": round(self.mechanism_plausibility_score, 4),
            "total_confidence_penalty": round(self.total_confidence_penalty, 4),
            "risk_level": self.risk_level,
            "plausibility_rationale": self.plausibility_rationale,
            "finding_count": len(self.findings),
            "findings": [
                {
                    "check_type": f.check_type,
                    "description": f.description,
                    "severity": f.severity,
                    "confidence_penalty": f.confidence_penalty,
                    "evidence_fragment": f.evidence_fragment,
                }
                for f in self.findings
            ],
        }


def _check_mechanism_plausibility(
    hypothesis_text: str,
    inference: MechanismInference | None,
    confidence: float,
) -> list[SemanticHallucinationFinding]:
    """
    Check whether the stated mechanism is plausible given the evidence.

    High confidence with low mechanism alignment is semantic hallucination:
    the system is asserting a causal story with certainty that the evidence
    does not support.
    """
    findings: list[SemanticHallucinationFinding] = []

    if inference is None:
        if confidence > 0.75:
            findings.append(
                SemanticHallucinationFinding(
                    check_type="mechanism_plausibility",
                    description=(
                        f"High confidence ({confidence:.2f}) but no operational mechanism "
                        "could be inferred from the evidence. The stated conclusion may not "
                        "be operationally grounded."
                    ),
                    severity="HIGH",
                    confidence_penalty=0.20,
                )
            )
        return findings

    mechanism_confidence = inference.mechanism_confidence

    # Confident nonsense: high hypothesis confidence + weak mechanism alignment
    if confidence > 0.80 and mechanism_confidence < 0.25:
        findings.append(
            SemanticHallucinationFinding(
                check_type="confident_nonsense",
                description=(
                    f"High hypothesis confidence ({confidence:.2f}) but mechanism "
                    f"alignment is weak ({mechanism_confidence:.2f}). "
                    "The hypothesis asserts a causal story with high certainty "
                    "that the evidence does not operationally support."
                ),
                severity="CRITICAL",
                confidence_penalty=0.30,
                evidence_fragment=hypothesis_text[:100] if hypothesis_text else "",
            )
        )

    # Moderate hallucination risk: medium-high confidence with poor mechanism alignment
    elif confidence > 0.60 and mechanism_confidence < 0.20:
        findings.append(
            SemanticHallucinationFinding(
                check_type="mechanism_evidence_mismatch",
                description=(
                    f"Moderate-high hypothesis confidence ({confidence:.2f}) but "
                    f"operational mechanism is poorly supported ({mechanism_confidence:.2f}). "
                    "The diagnosis may be plausible but lacks operational grounding."
                ),
                severity="HIGH",
                confidence_penalty=0.15,
            )
        )

    return findings


def _check_causal_chain_coherence(
    causal_chain: str,
    inference: MechanismInference | None,
) -> list[SemanticHallucinationFinding]:
    """
    Check whether the stated causal chain is operationally coherent.

    Detects chains that reference latent states or mechanisms that contradict
    what the evidence supports.
    """
    findings: list[SemanticHallucinationFinding] = []
    if not causal_chain or inference is None or inference.primary is None:
        return findings

    mechanism = inference.primary.mechanism
    lower_chain = causal_chain.lower()

    # Check if chain references mechanisms incompatible with the primary inference
    if inference.alternatives:
        alt_keywords = [
            kw
            for alt in inference.alternatives[:2]
            for kw in alt.mechanism.symptom_keywords[:3]
        ]
        primary_keywords = list(mechanism.symptom_keywords[:5])

        # If the chain uses more alternative keywords than primary keywords,
        # the chain may be inverting the evidence
        primary_hits = sum(1 for kw in primary_keywords if kw in lower_chain)
        alt_hits = sum(1 for kw in alt_keywords if kw in lower_chain)

        if alt_hits > primary_hits + 2 and primary_hits == 0:
            findings.append(
                SemanticHallucinationFinding(
                    check_type="causal_chain_mechanism_inversion",
                    description=(
                        "The causal chain description aligns more closely with an "
                        "alternative mechanism than the primary inferred mechanism. "
                        "The chain may be describing the wrong failure mode."
                    ),
                    severity="MEDIUM",
                    confidence_penalty=0.10,
                    evidence_fragment=causal_chain[:100],
                )
            )

    return findings


def _check_remediation_plausibility(
    remediation_text: str,
    inference: MechanismInference | None,
) -> list[SemanticHallucinationFinding]:
    """Check if remediation is operationally plausible for the inferred mechanism."""
    findings: list[SemanticHallucinationFinding] = []
    if not remediation_text or inference is None or inference.primary is None:
        return findings

    mechanism = inference.primary.mechanism
    lower = remediation_text.lower()

    # Check for presence of plausible remediations
    plausible_present = any(
        rem.replace("_", " ") in lower or rem in lower
        for rem in mechanism.plausible_remediations
    )

    # Check for incompatible remediations
    incompatible_found = [
        rem.replace("_", " ")
        for rem in mechanism.incompatible_remediations
        if rem.replace("_", " ") in lower or rem in lower
    ]

    if incompatible_found and not plausible_present:
        findings.append(
            SemanticHallucinationFinding(
                check_type="remediation_mechanism_implausibility",
                description=(
                    f"Remediation proposes actions that are incompatible with "
                    f"'{mechanism.name}' and no plausible remediation is present. "
                    f"Incompatible actions: {incompatible_found}. "
                    f"Expected: {list(mechanism.plausible_remediations[:2])}."
                ),
                severity="HIGH",
                confidence_penalty=0.20,
                evidence_fragment=remediation_text[:100],
            )
        )

    return findings


def _check_latent_state_consistency(
    evidence_items: list[dict[str, Any]],
    inference: MechanismInference | None,
) -> list[SemanticHallucinationFinding]:
    """Check if stated latent states are consistent with observable evidence."""
    findings: list[SemanticHallucinationFinding] = []
    if inference is None or not inference.latent_state_implications:
        return findings

    combined = " ".join(
        str(v)
        for item in evidence_items
        for k, v in item.items()
        if k in ("summary", "metric", "description", "signature")
    ).lower()

    # Latent state "heap_saturation" should not be inferred without any memory signals
    if "heap_saturation" in inference.latent_state_implications:
        memory_signals = ("memory", "heap", "gc", "oom")
        if not any(sig in combined for sig in memory_signals):
            findings.append(
                SemanticHallucinationFinding(
                    check_type="latent_state_unsupported",
                    description=(
                        "Latent state 'heap_saturation' is implied by the mechanism "
                        "but no memory or GC signals are present in evidence. "
                        "This latent state inference is unsupported."
                    ),
                    severity="MEDIUM",
                    confidence_penalty=0.10,
                )
            )

    # Latent state "consumer_saturation" without queue signals
    if "consumer_saturation" in inference.latent_state_implications:
        queue_signals = ("consumer lag", "kafka", "queue", "backpressure")
        if not any(sig in combined for sig in queue_signals):
            findings.append(
                SemanticHallucinationFinding(
                    check_type="latent_state_unsupported",
                    description=(
                        "Latent state 'consumer_saturation' is implied but no queue "
                        "or consumer lag signals are present in evidence."
                    ),
                    severity="MEDIUM",
                    confidence_penalty=0.10,
                )
            )

    return findings


class SemanticHallucinationChecker:
    """
    Checks for semantic hallucination in operational reasoning outputs.

    Complements the lexical hallucination detector with mechanism plausibility
    checks that identify confident-but-wrong operational reasoning.
    """

    def check(
        self,
        *,
        hypothesis_text: str,
        causal_chain: str,
        remediation_text: str,
        confidence: float,
        evidence_items: list[dict[str, Any]],
        inference: MechanismInference | None,
    ) -> SemanticHallucinationReport:
        findings: list[SemanticHallucinationFinding] = []

        findings.extend(
            _check_mechanism_plausibility(hypothesis_text, inference, confidence)
        )
        findings.extend(
            _check_causal_chain_coherence(causal_chain, inference)
        )
        findings.extend(
            _check_remediation_plausibility(remediation_text, inference)
        )
        findings.extend(
            _check_latent_state_consistency(evidence_items, inference)
        )

        total_penalty = sum(f.confidence_penalty for f in findings)
        mechanism_plausibility = (
            inference.mechanism_confidence if inference is not None else 0.0
        )

        # Risk level
        has_critical = any(f.severity == "CRITICAL" for f in findings)
        has_high = any(f.severity == "HIGH" for f in findings)

        if has_critical or total_penalty > 0.35:
            risk_level = "CRITICAL"
        elif has_high or total_penalty > 0.15:
            risk_level = "HIGH"
        elif findings:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        if findings:
            rationale = (
                f"{len(findings)} semantic issue(s) found. "
                f"Mechanism plausibility: {mechanism_plausibility:.2f}. "
                f"Total confidence penalty: {total_penalty:.2f}."
            )
        else:
            rationale = (
                f"No semantic hallucination detected. "
                f"Mechanism plausibility: {mechanism_plausibility:.2f}."
            )

        return SemanticHallucinationReport(
            findings=findings,
            mechanism_plausibility_score=round(mechanism_plausibility, 4),
            semantic_hallucination_detected=bool(findings),
            total_confidence_penalty=round(min(total_penalty, 0.60), 4),
            risk_level=risk_level,
            plausibility_rationale=rationale,
        )
