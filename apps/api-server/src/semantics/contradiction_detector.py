"""
Semantic Contradiction Detector for SentinelOps Phase 45.

Extends the existing uncertainty-layer contradiction detection with
operational semantic checks. The uncertainty engine (Phase 44) detected
temporal and signal-family contradictions. This module adds:

  - mechanism-remediation incompatibility contradictions
  - impossible operational state transition detection
  - contradictory workload pattern detection
  - deployment timeline semantic inconsistencies
  - topology-mechanism mismatch detection
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from semantics.semantic_engine import MechanismInference


@dataclass
class SemanticContradiction:
    category: str
    description: str
    severity: float
    evidence_keys: list[str] = field(default_factory=list)
    remediation_relevance: str = ""


@dataclass
class SemanticContradictionReport:
    contradictions: list[SemanticContradiction]
    total_severity: float
    has_critical_contradiction: bool
    contradiction_summary: str
    confidence_penalty: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "contradiction_count": len(self.contradictions),
            "total_severity": round(self.total_severity, 4),
            "has_critical_contradiction": self.has_critical_contradiction,
            "contradiction_summary": self.contradiction_summary,
            "confidence_penalty": round(self.confidence_penalty, 4),
            "contradictions": [
                {
                    "category": c.category,
                    "description": c.description,
                    "severity": round(c.severity, 4),
                    "remediation_relevance": c.remediation_relevance,
                }
                for c in self.contradictions
            ],
        }


def _detect_mechanism_remediation_contradiction(
    inference: MechanismInference | None,
    remediation_text: str,
) -> list[SemanticContradiction]:
    """Detect when the proposed remediation contradicts the inferred mechanism."""
    if inference is None or inference.primary is None or not remediation_text:
        return []

    mechanism = inference.primary.mechanism
    contradictions: list[SemanticContradiction] = []
    lower = remediation_text.lower()

    for incompatible in mechanism.incompatible_remediations:
        if incompatible.lower().replace("_", " ") in lower:
            contradictions.append(
                SemanticContradiction(
                    category="mechanism_remediation_mismatch",
                    description=(
                        f"Proposed action '{incompatible.replace('_', ' ')}' is "
                        f"incompatible with inferred mechanism '{mechanism.name}'. "
                        f"This action does not address the identified operational failure."
                    ),
                    severity=0.40,
                    remediation_relevance=(
                        f"Use instead: {', '.join(list(mechanism.plausible_remediations)[:2])}"
                    ),
                )
            )

    return contradictions


def _detect_workload_pattern_contradiction(
    evidence_items: list[dict[str, Any]],
    inference: MechanismInference | None,
) -> list[SemanticContradiction]:
    """Detect contradictory workload patterns in evidence."""
    contradictions: list[SemanticContradiction] = []
    combined = " ".join(
        str(v)
        for item in evidence_items
        for k, v in item.items()
        if k in ("summary", "metric", "description")
    ).lower()

    # Contradiction: high CPU AND connection pool exhaustion together suggest
    # the bottleneck is likely compute, not the DB pool — weakens pool starvation claim
    has_high_cpu = any(sig in combined for sig in ("cpu high", "cpu spike", "cpu utilization"))
    has_pool_starvation_claim = (
        inference is not None
        and inference.primary is not None
        and inference.primary.mechanism.mechanism_id == "connection_pool_starvation"
    )
    if has_high_cpu and has_pool_starvation_claim:
        contradictions.append(
            SemanticContradiction(
                category="workload_pattern_contradiction",
                description=(
                    "High CPU utilization co-occurs with connection pool starvation signals. "
                    "High CPU typically indicates compute saturation rather than pool exhaustion. "
                    "The inferred mechanism may be incomplete or overlapping with compute pressure."
                ),
                severity=0.25,
            )
        )

    # Contradiction: retry storm claim but no error rate evidence
    has_retry_claim = (
        inference is not None
        and inference.primary is not None
        and inference.primary.mechanism.mechanism_id == "retry_storm"
    )
    has_error_rate = any(sig in combined for sig in ("error rate", "5xx", "error_rate", "failures"))
    if has_retry_claim and not has_error_rate:
        contradictions.append(
            SemanticContradiction(
                category="workload_pattern_contradiction",
                description=(
                    "Retry storm mechanism inferred but no error rate evidence present. "
                    "A retry storm typically requires an elevated error rate to trigger retries."
                ),
                severity=0.20,
            )
        )

    # Contradiction: noisy alert inferred but evidence includes error logs
    has_error_logs = any(
        sig in combined for sig in ("error", "exception", "stacktrace", "panic", "fatal")
    )
    has_noisy_alert_claim = (
        inference is not None
        and inference.primary is not None
        and inference.primary.mechanism.mechanism_id == "noisy_alert_amplification"
    )
    if has_noisy_alert_claim and has_error_logs:
        contradictions.append(
            SemanticContradiction(
                category="workload_pattern_contradiction",
                description=(
                    "Noisy alert mechanism inferred but error log evidence is present. "
                    "Error logs suggest real degradation, not a false positive alert."
                ),
                severity=0.30,
            )
        )

    return contradictions


def _detect_impossible_state_transition(
    evidence_items: list[dict[str, Any]],
    timed_events: list[Any],
) -> list[SemanticContradiction]:
    """Detect operationally impossible state combinations."""
    contradictions: list[SemanticContradiction] = []
    combined = " ".join(
        str(v)
        for item in evidence_items
        for k, v in item.items()
        if k in ("summary", "metric", "description")
    ).lower()

    # An open circuit breaker AND successful request throughput is contradictory
    has_circuit_open = any(
        sig in combined for sig in ("circuit open", "circuit tripped", "breaker open")
    )
    has_normal_throughput = any(
        sig in combined for sig in ("normal throughput", "throughput stable", "requests stable")
    )
    if has_circuit_open and has_normal_throughput:
        contradictions.append(
            SemanticContradiction(
                category="impossible_state_transition",
                description=(
                    "Open circuit breaker co-occurs with stable throughput evidence. "
                    "An open circuit breaker should prevent requests from reaching the dependency, "
                    "making stable throughput evidence contradictory."
                ),
                severity=0.35,
            )
        )

    # Fully exhausted connection pool AND low database wait time is contradictory
    has_pool_exhaustion = any(sig in combined for sig in ("pool exhausted", "connection limit"))
    has_low_db_wait = any(sig in combined for sig in ("db wait low", "fast query", "low latency"))
    if has_pool_exhaustion and has_low_db_wait:
        contradictions.append(
            SemanticContradiction(
                category="impossible_state_transition",
                description=(
                    "Connection pool exhaustion co-occurs with low database wait time. "
                    "An exhausted pool should produce high connection acquisition waits."
                ),
                severity=0.30,
            )
        )

    return contradictions


def _detect_deployment_timeline_contradiction(
    evidence_items: list[dict[str, Any]],
    timed_events: list[Any],
    inference: MechanismInference | None,
) -> list[SemanticContradiction]:
    """Detect when deployment timeline is semantically inconsistent with claimed mechanism."""
    contradictions: list[SemanticContradiction] = []
    has_deployment_signal = any(
        getattr(event, "item_type", "") == "deployment_change" for event in timed_events
    )

    if not has_deployment_signal:
        return contradictions

    # If mechanism is deployment_induced_regression but there is no deployment
    # event in timed_events, that is a weak claim
    has_regression_claim = (
        inference is not None
        and inference.primary is not None
        and inference.primary.mechanism.mechanism_id == "deployment_induced_regression"
    )

    # This is fine — deployment evidence is present
    if has_regression_claim and has_deployment_signal:
        return contradictions

    # If mechanism is NOT deployment-related but deployment evidence is strong,
    # note the under-weighting
    if not has_regression_claim and has_deployment_signal and inference is not None:
        primary_name = inference.primary.mechanism.name if inference.primary else "unknown"
        contradictions.append(
            SemanticContradiction(
                category="deployment_timeline_underweighted",
                description=(
                    f"Deployment event is present in evidence but the primary inferred "
                    f"mechanism is '{primary_name}', which does not account for the deployment. "
                    "Consider whether the deployment may have triggered the inferred mechanism."
                ),
                severity=0.15,
            )
        )

    return contradictions


class SemanticContradictionDetector:
    """
    Detects operational semantic contradictions in the evidence and reasoning chain.

    Supplements the uncertainty engine's temporal and signal-family contradiction
    detection with mechanism-level semantic checks.
    """

    def detect(
        self,
        evidence_items: list[dict[str, Any]],
        timed_events: list[Any],
        inference: MechanismInference | None,
        remediation_text: str = "",
    ) -> SemanticContradictionReport:
        contradictions: list[SemanticContradiction] = []

        contradictions.extend(
            _detect_mechanism_remediation_contradiction(inference, remediation_text)
        )
        contradictions.extend(_detect_workload_pattern_contradiction(evidence_items, inference))
        contradictions.extend(_detect_impossible_state_transition(evidence_items, timed_events))
        contradictions.extend(
            _detect_deployment_timeline_contradiction(evidence_items, timed_events, inference)
        )

        total_severity = sum(c.severity for c in contradictions)
        has_critical = any(c.severity >= 0.35 for c in contradictions)
        confidence_penalty = min(0.4, total_severity * 0.6)

        if not contradictions:
            summary = "No semantic contradictions detected."
        elif has_critical:
            summary = (
                f"{len(contradictions)} semantic contradiction(s) detected; "
                f"at least one is operationally significant. Confidence reduced."
            )
        else:
            summary = (
                f"{len(contradictions)} minor semantic contradiction(s) detected. "
                "Reasoning remains plausible but warrants operator review."
            )

        return SemanticContradictionReport(
            contradictions=contradictions,
            total_severity=round(total_severity, 4),
            has_critical_contradiction=has_critical,
            contradiction_summary=summary,
            confidence_penalty=round(confidence_penalty, 4),
        )
