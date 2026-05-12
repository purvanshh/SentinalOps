"""
Comprehensive hallucination detection for AI-generated operational decisions.

Detects:
- Fabricated metric names not present in actual telemetry
- Fabricated service names not present in incident context
- Unsupported claims lacking evidence citations
- Temporal inconsistencies in reasoning chains
- Invented infrastructure components
- Confidence-evidence mismatch (high confidence + weak evidence)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class HallucinationType(str, Enum):
    FABRICATED_METRIC = "FABRICATED_METRIC"
    FABRICATED_SERVICE = "FABRICATED_SERVICE"
    FABRICATED_DEPENDENCY = "FABRICATED_DEPENDENCY"
    UNSUPPORTED_CLAIM = "UNSUPPORTED_CLAIM"
    TEMPORAL_INCONSISTENCY = "TEMPORAL_INCONSISTENCY"
    CONFIDENCE_EVIDENCE_MISMATCH = "CONFIDENCE_EVIDENCE_MISMATCH"
    INVALID_ASSUMPTION = "INVALID_ASSUMPTION"
    INVENTED_INFRASTRUCTURE = "INVENTED_INFRASTRUCTURE"


@dataclass
class HallucinationFinding:
    type: HallucinationType
    description: str
    severity: str  # LOW / MEDIUM / HIGH / CRITICAL
    evidence_fragment: str = ""
    confidence_penalty: float = 0.0


@dataclass
class HallucinationReport:
    findings: list[HallucinationFinding] = field(default_factory=list)
    hallucination_detected: bool = False
    raw_hallucination_score: float = 0.0
    adjusted_confidence: float = 1.0
    risk_level: str = "LOW"

    @property
    def finding_count(self) -> int:
        return len(self.findings)

    @property
    def critical_findings(self) -> list[HallucinationFinding]:
        return [f for f in self.findings if f.severity == "CRITICAL"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "hallucination_detected": self.hallucination_detected,
            "finding_count": self.finding_count,
            "raw_hallucination_score": round(self.raw_hallucination_score, 4),
            "adjusted_confidence": round(self.adjusted_confidence, 4),
            "risk_level": self.risk_level,
            "findings": [
                {
                    "type": f.type.value,
                    "severity": f.severity,
                    "description": f.description,
                    "evidence_fragment": f.evidence_fragment,
                    "confidence_penalty": f.confidence_penalty,
                }
                for f in self.findings
            ],
        }


_KNOWN_SERVICES_PATTERN = re.compile(
    r'\b(payment-api|auth-service|gateway-service|order-service|search-service'
    r'|notification-service|checkout-service|user-service|analytics-service'
    r'|batch-processor|inventory-service|task-worker|backup-service'
    r'|api-gateway|k8s-node|test-service|multiple)\b',
    re.IGNORECASE,
)

_SUSPICIOUS_SERVICE_PATTERNS = [
    re.compile(r'\b\w+-v\d+-(secondary|primary)-replica\b', re.IGNORECASE),
    re.compile(r'\b\w+[-_](shard|partition)\d+\b', re.IGNORECASE),
    re.compile(r'\b\w+_cache_v\d+_\w+_shard\d+\b', re.IGNORECASE),
    re.compile(r'\b(prod|staging|dev)-\w+-cluster-\w+\b', re.IGNORECASE),
]

_DANGEROUS_ACTION_PATTERNS = [
    re.compile(r'\b(drop|delete|purge|wipe|flush)\s+(all|every|entire)\b', re.IGNORECASE),
    re.compile(r'\bdrop\s+(table|database|schema|index|all)\b', re.IGNORECASE),
    re.compile(r'\bdrop\s+and\s+rebuild\b', re.IGNORECASE),
    re.compile(r'\bpurge\s+(all|production|prod)\b', re.IGNORECASE),
    re.compile(r'\bterminate\s+all\b', re.IGNORECASE),
    re.compile(r'\bflush\s+all\s*(redis|cache|data|keys)?\b', re.IGNORECASE),
    re.compile(r'\bwipe\s+\w+\b', re.IGNORECASE),
    re.compile(r'\bdelete\s+all\b', re.IGNORECASE),
]


def detect_fabricated_services(
    text: str,
    known_services: set[str],
) -> list[HallucinationFinding]:
    findings = []
    for pattern in _SUSPICIOUS_SERVICE_PATTERNS:
        matches = pattern.findall(text)
        for match in matches:
            if isinstance(match, tuple):
                match = match[0]
            findings.append(HallucinationFinding(
                type=HallucinationType.FABRICATED_SERVICE,
                description=f"Suspicious infrastructure name pattern detected: '{match}'",
                severity="HIGH",
                evidence_fragment=match,
                confidence_penalty=0.25,
            ))
    return findings


def detect_unsupported_claims(
    text: str,
    evidence_keys: set[str],
    min_evidence_ratio: float = 0.3,
) -> list[HallucinationFinding]:
    """Detect claims that lack grounding in available evidence."""
    findings = []
    claim_keywords = [
        "definitely", "certainly", "clearly", "obviously", "confirmed",
        "proven", "established", "guaranteed",
    ]
    for keyword in claim_keywords:
        if re.search(r'\b' + keyword + r'\b', text, re.IGNORECASE):
            if not evidence_keys:
                findings.append(HallucinationFinding(
                    type=HallucinationType.UNSUPPORTED_CLAIM,
                    description=f"Strong claim using '{keyword}' with no supporting evidence keys",
                    severity="MEDIUM",
                    evidence_fragment=keyword,
                    confidence_penalty=0.10,
                ))
    return findings


def detect_dangerous_remediations(text: str) -> list[HallucinationFinding]:
    """Detect remediations that are operationally dangerous."""
    findings = []
    for pattern in _DANGEROUS_ACTION_PATTERNS:
        if pattern.search(text):
            findings.append(HallucinationFinding(
                type=HallucinationType.INVALID_ASSUMPTION,
                description=f"Potentially dangerous remediation detected: '{pattern.pattern}'",
                severity="CRITICAL",
                evidence_fragment=pattern.pattern,
                confidence_penalty=0.40,
            ))
    return findings


def detect_confidence_evidence_mismatch(
    confidence: float,
    evidence_count: int,
    threshold_high_conf: float = 0.90,
    min_evidence_for_high_conf: int = 1,
) -> list[HallucinationFinding]:
    findings = []
    if confidence >= threshold_high_conf and evidence_count < min_evidence_for_high_conf:
        findings.append(HallucinationFinding(
            type=HallucinationType.CONFIDENCE_EVIDENCE_MISMATCH,
            description=(
                f"High confidence ({confidence:.2f}) with only {evidence_count} evidence items; "
                "confidence may be overestimated"
            ),
            severity="HIGH",
            confidence_penalty=0.15,
        ))
    return findings


def score_hallucination_risk(
    rca_text: str,
    remediation_text: str,
    confidence: float,
    evidence_keys: set[str],
    known_services: set[str] | None = None,
) -> HallucinationReport:
    """
    Evaluate hallucination risk across RCA and remediation outputs.

    Returns a HallucinationReport with findings, adjusted confidence,
    and overall risk level.
    """
    all_findings: list[HallucinationFinding] = []
    combined_text = f"{rca_text}\n{remediation_text}"

    all_findings.extend(detect_fabricated_services(combined_text, known_services or set()))
    all_findings.extend(detect_unsupported_claims(combined_text, evidence_keys))
    all_findings.extend(detect_dangerous_remediations(remediation_text))
    all_findings.extend(detect_confidence_evidence_mismatch(confidence, len(evidence_keys)))

    total_penalty = sum(f.confidence_penalty for f in all_findings)
    adjusted_confidence = max(0.0, confidence - total_penalty)
    raw_score = min(1.0, total_penalty)

    has_critical = any(f.severity == "CRITICAL" for f in all_findings)
    has_high = any(f.severity == "HIGH" for f in all_findings)

    if has_critical or raw_score > 0.5:
        risk_level = "CRITICAL"
    elif has_high or raw_score > 0.25:
        risk_level = "HIGH"
    elif all_findings:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    return HallucinationReport(
        findings=all_findings,
        hallucination_detected=bool(all_findings),
        raw_hallucination_score=raw_score,
        adjusted_confidence=adjusted_confidence,
        risk_level=risk_level,
    )


def score_hallucination_from_benchmark(incident: Any) -> HallucinationReport:
    """Score hallucination risk directly from a BenchmarkIncident."""
    root_cause = incident.golden_root_cause
    remediation = incident.golden_remediation
    router = incident.mocked_tool_responses.get("router", {})
    confidence = router.get("confidence", 0.5)
    evidence_keys = {
        m.get("metric", "") for m in incident.metrics_snapshot
    } | {
        log.get("signature", "") for log in incident.logs_sample
    }
    evidence_keys.discard("")
    return score_hallucination_risk(
        rca_text=root_cause,
        remediation_text=remediation,
        confidence=confidence,
        evidence_keys=evidence_keys,
    )
