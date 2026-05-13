"""
Operational uncertainty modeling for SentinelOps agents.

Phase 44 extends the original evidence-quality indicator into a shared
uncertainty engine that can:
  - aggregate uncertainty sources
  - score contradictory evidence
  - collapse confidence when telemetry is incomplete
  - distribute probability across competing hypotheses
  - recommend operator escalation when ambiguity is unsafe
"""

from __future__ import annotations

import math
from statistics import mean
from typing import Literal

from pydantic import BaseModel, Field

UncertaintyStatus = Literal["present", "partial", "unavailable", "conflicting"]
OperationalUncertaintyState = Literal[
    "stable",
    "unknown_cause",
    "insufficient_telemetry",
    "conflicting_signals",
    "low_confidence_escalation",
]

UNKNOWN_CAUSE = "unknown_cause"
INSUFFICIENT_TELEMETRY = "insufficient_telemetry"
CONFLICTING_SIGNALS = "conflicting_signals"
LOW_CONFIDENCE_ESCALATION = "low_confidence_escalation"

_METRIC_TYPES = frozenset({"metric_anomaly"})
_LOG_TYPES = frozenset({"error_signature"})
_DEPLOYMENT_TYPES = frozenset({"deployment_change"})
_DB_KEYWORDS = ("postgres", "database", "pool", "connection", "query", "db")
_DEPLOYMENT_KEYWORDS = ("deploy", "rollback", "release", "migration", "config")
_NETWORK_KEYWORDS = ("network", "dns", "packet", "latency", "timeout")


class UncertaintyIndicator(BaseModel):
    """Describes the quality and completeness of an agent's evidence collection."""

    status: UncertaintyStatus
    reason: str = ""
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)

    @classmethod
    def present(cls) -> "UncertaintyIndicator":
        return cls(status="present", confidence=1.0)

    @classmethod
    def partial(cls, reason: str, confidence: float = 0.6) -> "UncertaintyIndicator":
        return cls(status="partial", reason=reason, confidence=confidence)

    @classmethod
    def unavailable(cls, reason: str) -> "UncertaintyIndicator":
        return cls(status="unavailable", reason=reason, confidence=0.0)

    @classmethod
    def conflicting(cls, reason: str, confidence: float = 0.4) -> "UncertaintyIndicator":
        return cls(status="conflicting", reason=reason, confidence=confidence)

    @property
    def is_actionable(self) -> bool:
        """Return True when evidence is sufficient to support a reasoning step."""
        return self.status in ("present", "partial") and self.confidence >= 0.3


class ConfidenceInterval(BaseModel):
    lower: float = Field(ge=0.0, le=1.0)
    upper: float = Field(ge=0.0, le=1.0)


class UncertaintySource(BaseModel):
    source: str
    reason: str
    weight: float = Field(ge=0.0, le=1.0, default=0.0)
    penalty: float = Field(ge=0.0, le=1.0, default=0.0)
    evidence_keys: list[str] = Field(default_factory=list)


class EvidenceContradiction(BaseModel):
    category: str
    description: str
    severity: float = Field(ge=0.0, le=1.0, default=0.2)
    evidence_keys: list[str] = Field(default_factory=list)


class EscalationDecision(BaseModel):
    recommended: bool = False
    state: OperationalUncertaintyState = "stable"
    reasons: list[str] = Field(default_factory=list)
    triggers: list[str] = Field(default_factory=list)
    confidence_threshold: float = Field(ge=0.0, le=1.0, default=0.55)


class UncertaintyAssessment(BaseModel):
    state: OperationalUncertaintyState = "stable"
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    uncertainty_score: float = Field(ge=0.0, le=1.0, default=0.0)
    evidence_sufficiency: float = Field(ge=0.0, le=1.0, default=0.0)
    retrieval_grounding: float = Field(ge=0.0, le=1.0, default=0.0)
    hypothesis_stability: float = Field(ge=0.0, le=1.0, default=0.0)
    confidence_interval: ConfidenceInterval = Field(
        default_factory=lambda: ConfidenceInterval(lower=0.0, upper=0.0)
    )
    missing_telemetry: list[str] = Field(default_factory=list)
    sources: list[UncertaintySource] = Field(default_factory=list)
    contradictions: list[EvidenceContradiction] = Field(default_factory=list)
    alternative_explanations: list[str] = Field(default_factory=list)
    escalation: EscalationDecision = Field(default_factory=EscalationDecision)
    rationale: list[str] = Field(default_factory=list)


def infer_uncertainty_from_items(items: list[dict]) -> UncertaintyIndicator:
    """
    Derive an UncertaintyIndicator from a list of normalised evidence items.

    Rules:
    - No items -> unavailable
    - All items have uncertainty_status partial -> partial
    - Any conflicting item present -> conflicting
    - Otherwise -> present, with confidence = mean of item confidences
    """
    if not items:
        return UncertaintyIndicator.unavailable("no evidence items produced by agent")

    statuses = [item.get("uncertainty_status", "present") for item in items]
    confidences = [float(item.get("confidence", 1.0)) for item in items]

    if "conflicting" in statuses:
        return UncertaintyIndicator.conflicting(
            "conflicting evidence items detected",
            confidence=sum(confidences) / len(confidences),
        )

    if all(status == "partial" for status in statuses):
        return UncertaintyIndicator.partial(
            "all evidence items have partial provenance",
            confidence=sum(confidences) / len(confidences),
        )

    if all(status == "unavailable" for status in statuses):
        return UncertaintyIndicator.unavailable("all evidence items are unavailable")

    mean_confidence = round(sum(confidences) / len(confidences), 3)
    if all(status in ("present", "partial") for status in statuses):
        if mean_confidence < 0.5:
            return UncertaintyIndicator.partial(
                "low mean confidence across evidence items",
                confidence=mean_confidence,
            )
        return UncertaintyIndicator(status="present", confidence=mean_confidence)

    return UncertaintyIndicator(
        status="partial",
        reason="mixed evidence quality",
        confidence=mean_confidence,
    )


def apply_temperature_scaling(probability: float, temperature: float = 1.0) -> float:
    """Calibrate a binary confidence score using temperature scaling."""
    bounded = min(max(probability, 1e-6), 1.0 - 1e-6)
    if temperature <= 0:
        temperature = 1.0
    logit = math.log(bounded / (1.0 - bounded))
    scaled = 1.0 / (1.0 + math.exp(-(logit / temperature)))
    return round(min(max(scaled, 0.0), 1.0), 4)


def distribute_probabilities(
    scores: list[float],
    *,
    temperature: float = 1.0,
) -> list[float]:
    """Convert arbitrary non-negative scores into a temperature-scaled distribution."""
    if not scores:
        return []
    safe_scores = [max(score, 1e-6) for score in scores]
    if temperature <= 0:
        temperature = 1.0
    logits = [math.log(score) / temperature for score in safe_scores]
    max_logit = max(logits)
    exps = [math.exp(logit - max_logit) for logit in logits]
    total = sum(exps) or 1.0
    return [round(value / total, 4) for value in exps]


class UncertaintyEngine:
    """Aggregate uncertainty, calibrate confidence, and recommend escalation."""

    def __init__(
        self,
        *,
        calibration_temperature: float = 1.35,
        escalation_threshold: float = 0.55,
    ) -> None:
        self.calibration_temperature = calibration_temperature
        self.escalation_threshold = escalation_threshold

    def rank_hypotheses(self, raw_scores: list[float]) -> list[float]:
        return distribute_probabilities(
            raw_scores,
            temperature=self.calibration_temperature,
        )

    def confidence_interval(
        self,
        confidence: float,
        uncertainty_score: float,
        contradiction_count: int = 0,
    ) -> ConfidenceInterval:
        width = min(0.45, 0.08 + (uncertainty_score * 0.30) + (contradiction_count * 0.03))
        return ConfidenceInterval(
            lower=round(max(0.0, confidence - width), 4),
            upper=round(min(1.0, confidence + width), 4),
        )

    def assess(
        self,
        *,
        evidence_items: list[dict],
        timed_events: list,
        grounding_score: float,
        raw_hypothesis_scores: list[float],
        hypothesis_labels: list[str],
        incident_severity: str | None = None,
    ) -> UncertaintyAssessment:
        sources = self._collect_sources(
            evidence_items=evidence_items,
            timed_events=timed_events,
            grounding_score=grounding_score,
            raw_hypothesis_scores=raw_hypothesis_scores,
            hypothesis_labels=hypothesis_labels,
        )
        contradictions = self._detect_contradictions(timed_events, hypothesis_labels)
        missing_telemetry = self._missing_telemetry(evidence_items)
        probabilities = self.rank_hypotheses(raw_hypothesis_scores)
        top_confidence = probabilities[0] if probabilities else 0.0
        evidence_sufficiency = self._evidence_sufficiency(evidence_items, missing_telemetry)
        stability = self._hypothesis_stability(probabilities)
        uncertainty_score = self._aggregate_uncertainty_score(
            sources=sources,
            contradictions=contradictions,
            missing_telemetry=missing_telemetry,
            stability=stability,
        )
        calibrated_confidence = apply_temperature_scaling(
            top_confidence * max(evidence_sufficiency, 0.2) * max(grounding_score, 0.2),
            self.calibration_temperature,
        )
        state = self._resolve_state(
            calibrated_confidence=calibrated_confidence,
            missing_telemetry=missing_telemetry,
            contradictions=contradictions,
            stability=stability,
        )
        escalation = self._build_escalation(
            state=state,
            confidence=calibrated_confidence,
            contradictions=contradictions,
            grounding_score=grounding_score,
            incident_severity=incident_severity,
        )
        return UncertaintyAssessment(
            state=state,
            confidence=calibrated_confidence,
            uncertainty_score=uncertainty_score,
            evidence_sufficiency=evidence_sufficiency,
            retrieval_grounding=round(grounding_score, 4),
            hypothesis_stability=stability,
            confidence_interval=self.confidence_interval(
                calibrated_confidence,
                uncertainty_score,
                len(contradictions),
            ),
            missing_telemetry=missing_telemetry,
            sources=sources,
            contradictions=contradictions,
            alternative_explanations=hypothesis_labels[1:4],
            escalation=escalation,
            rationale=[source.reason for source in sources]
            + [contradiction.description for contradiction in contradictions],
        )

    def _collect_sources(
        self,
        *,
        evidence_items: list[dict],
        timed_events: list,
        grounding_score: float,
        raw_hypothesis_scores: list[float],
        hypothesis_labels: list[str],
    ) -> list[UncertaintySource]:
        sources: list[UncertaintySource] = []
        missing = self._missing_telemetry(evidence_items)
        for source_name in missing:
            sources.append(
                UncertaintySource(
                    source="missing_telemetry",
                    reason=f"Missing {source_name} evidence reduces attribution reliability.",
                    weight=0.8,
                    penalty=0.22,
                )
            )

        if grounding_score < 0.45:
            sources.append(
                UncertaintySource(
                    source="weak_grounding",
                    reason=(
                        "Historical retrieval grounding is weak, so similar "
                        "incidents may be misleading."
                    ),
                    weight=0.9,
                    penalty=0.26,
                )
            )
        elif grounding_score < 0.60:
            sources.append(
                UncertaintySource(
                    source="partial_grounding",
                    reason="Retrieved evidence is only moderately similar to the active incident.",
                    weight=0.5,
                    penalty=0.12,
                )
            )

        if len(evidence_items) < 3:
            sources.append(
                UncertaintySource(
                    source="sparse_evidence",
                    reason=(
                        "Evidence volume is sparse, so confidence should "
                        "collapse toward operator review."
                    ),
                    weight=0.7,
                    penalty=0.18,
                    evidence_keys=[item.get("item_key", "") for item in evidence_items],
                )
            )

        if len(raw_hypothesis_scores) > 1:
            ranked = sorted(raw_hypothesis_scores, reverse=True)
            if abs(ranked[0] - ranked[1]) < 0.12:
                sources.append(
                    UncertaintySource(
                        source="multi_hypothesis_ambiguity",
                        reason="Multiple competing hypotheses are similarly plausible.",
                        weight=0.8,
                        penalty=0.20,
                    )
                )

        if len(hypothesis_labels) == 1 and "unknown" in hypothesis_labels[0].lower():
            sources.append(
                UncertaintySource(
                    source="unknown_unknowns",
                    reason=(
                        "The evidence collapses into a generic degradation "
                        "pattern instead of a stable root cause."
                    ),
                    weight=0.9,
                    penalty=0.28,
                )
            )

        event_summaries = " ".join(getattr(event, "summary", "") for event in timed_events).lower()
        signal_families = 0
        for keywords in (_DB_KEYWORDS, _DEPLOYMENT_KEYWORDS, _NETWORK_KEYWORDS):
            if any(keyword in event_summaries for keyword in keywords):
                signal_families += 1
        if signal_families >= 2:
            sources.append(
                UncertaintySource(
                    source="conflicting_signal_families",
                    reason="Telemetry supports more than one operational failure family.",
                    weight=0.7,
                    penalty=0.16,
                )
            )

        return sources

    def _detect_contradictions(
        self,
        timed_events: list,
        hypothesis_labels: list[str],
    ) -> list[EvidenceContradiction]:
        contradictions: list[EvidenceContradiction] = []
        anomaly_events = [
            event
            for event in timed_events
            if getattr(event, "item_type", "") in (_METRIC_TYPES | _LOG_TYPES)
        ]
        deployment_events = [
            event for event in timed_events if getattr(event, "item_type", "") in _DEPLOYMENT_TYPES
        ]
        if anomaly_events and deployment_events:
            first_anomaly = min(
                (event.timestamp for event in anomaly_events if event.timestamp is not None),
                default=None,
            )
            latest_deployment = max(
                (event.timestamp for event in deployment_events if event.timestamp is not None),
                default=None,
            )
            if (
                first_anomaly is not None
                and latest_deployment is not None
                and latest_deployment > first_anomaly
                and any("deploy" in label.lower() for label in hypothesis_labels)
            ):
                contradictions.append(
                    EvidenceContradiction(
                        category="temporal_contradiction",
                        description=(
                            "Deployment evidence occurred after the earliest anomaly, "
                            "so a deployment-only attribution is temporally unstable."
                        ),
                        severity=0.35,
                        evidence_keys=[event.item_key for event in deployment_events[:2]],
                    )
                )

        event_summaries = " ".join(getattr(event, "summary", "") for event in timed_events).lower()
        if any(keyword in event_summaries for keyword in _DB_KEYWORDS) and any(
            keyword in event_summaries for keyword in _DEPLOYMENT_KEYWORDS
        ):
            contradictions.append(
                EvidenceContradiction(
                    category="conflicting_operational_signals",
                    description=(
                        "Database saturation and deployment regression signals are both present."
                    ),
                    severity=0.22,
                )
            )
        return contradictions

    def _missing_telemetry(self, evidence_items: list[dict]) -> list[str]:
        present_types = {item.get("item_type", "") for item in evidence_items}
        missing: list[str] = []
        if not present_types & _METRIC_TYPES:
            missing.append("metrics")
        if not present_types & _LOG_TYPES:
            missing.append("logs")
        if not present_types & _DEPLOYMENT_TYPES:
            missing.append("deployments")
        return missing

    def _evidence_sufficiency(
        self,
        evidence_items: list[dict],
        missing_telemetry: list[str],
    ) -> float:
        if not evidence_items:
            return 0.0
        mean_confidence = mean(float(item.get("confidence", 0.6)) for item in evidence_items)
        missing_penalty = min(0.45, 0.15 * len(missing_telemetry))
        return round(max(0.0, min(1.0, mean_confidence - missing_penalty)), 4)

    def _hypothesis_stability(self, probabilities: list[float]) -> float:
        if not probabilities:
            return 0.0
        if len(probabilities) == 1:
            return round(probabilities[0], 4)
        ordered = sorted(probabilities, reverse=True)
        return round(max(0.0, ordered[0] - ordered[1]), 4)

    def _aggregate_uncertainty_score(
        self,
        *,
        sources: list[UncertaintySource],
        contradictions: list[EvidenceContradiction],
        missing_telemetry: list[str],
        stability: float,
    ) -> float:
        penalty = sum(source.penalty * source.weight for source in sources)
        penalty += sum(item.severity for item in contradictions)
        penalty += min(0.3, 0.08 * len(missing_telemetry))
        penalty += max(0.0, 0.18 - stability)
        return round(min(1.0, penalty), 4)

    def _resolve_state(
        self,
        *,
        calibrated_confidence: float,
        missing_telemetry: list[str],
        contradictions: list[EvidenceContradiction],
        stability: float,
    ) -> OperationalUncertaintyState:
        if len(missing_telemetry) >= 2:
            return INSUFFICIENT_TELEMETRY
        if contradictions:
            return CONFLICTING_SIGNALS
        if calibrated_confidence < 0.35 and stability < 0.1:
            return UNKNOWN_CAUSE
        if calibrated_confidence < self.escalation_threshold:
            return LOW_CONFIDENCE_ESCALATION
        return "stable"

    def _build_escalation(
        self,
        *,
        state: OperationalUncertaintyState,
        confidence: float,
        contradictions: list[EvidenceContradiction],
        grounding_score: float,
        incident_severity: str | None,
    ) -> EscalationDecision:
        triggers: list[str] = []
        reasons: list[str] = []
        if confidence < self.escalation_threshold:
            triggers.append("low_confidence")
            reasons.append("Confidence is below the safe autonomy threshold.")
        if contradictions:
            triggers.append("conflicting_evidence")
            reasons.append("Evidence contains contradictions that make autonomous action unsafe.")
        if grounding_score < 0.50:
            triggers.append("weak_retrieval_grounding")
            reasons.append("Historical retrieval grounding is too weak for decisive attribution.")
        if incident_severity and incident_severity.lower() in {"critical", "sev1", "high"}:
            triggers.append("high_blast_radius")
            reasons.append("The incident severity suggests a high blast-radius scenario.")
        if state in {UNKNOWN_CAUSE, INSUFFICIENT_TELEMETRY, CONFLICTING_SIGNALS}:
            triggers.append(state)
        return EscalationDecision(
            recommended=bool(triggers),
            state=state,
            reasons=reasons,
            triggers=triggers,
            confidence_threshold=self.escalation_threshold,
        )
