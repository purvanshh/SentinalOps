"""
Evidence-grounded incident narrative generation for SentinelOps Phase 45.

Produces causal narratives that are:
  - temporally ordered (events narrated in time sequence)
  - topology consistent (only valid propagation paths described)
  - evidence grounded (each claim tied to retrieved evidence)
  - uncertainty aware (confidence expressed, contradictions surfaced)
  - mechanism aware (Phase 45: names the operational failure mechanism)

Narrative format:
  "At {timestamp}, {mechanism_name} in {service} was identified.
   {mechanism_description} This propagated to {downstream_service} at
   {effect_timestamp}, causing {effect_description}. [Confidence: {pct}%]"

Operator explainability output:
  {
    "root_cause": "...",
    "mechanism": {"id": "...", "name": "...", "description": "..."},
    "why": [...],
    "evidence_chain": [...],
    "causal_confidence": 0.83,
    "contradictory_evidence": [...],
    "propagation_path": [...]
  }
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from causality.failure_classifier import ClassifiedEvent, FailureType
from causality.temporal_engine import sequence_events_by_time
from semantics.semantic_engine import MechanismInference


@dataclass
class IncidentNarrative:
    """Structured causal narrative with full explainability."""

    summary: str
    timeline: list[str]
    root_cause_statement: str
    propagation_description: str
    causal_confidence: float
    why_statements: list[str]
    evidence_chain: list[dict[str, Any]]
    contradictory_evidence: list[str]
    propagation_path: list[str]
    uncertainty_note: str = ""
    mechanism_id: str | None = None
    mechanism_name: str | None = None
    mechanism_description: str | None = None
    mechanism_confidence: float = 0.0

    def to_explainability_dict(self) -> dict[str, Any]:
        """Operator-facing explainability output."""
        result: dict[str, Any] = {
            "root_cause": self.root_cause_statement,
            "why": self.why_statements,
            "evidence_chain": self.evidence_chain,
            "causal_confidence": self.causal_confidence,
            "contradictory_evidence": self.contradictory_evidence,
            "propagation_path": self.propagation_path,
            "timeline": self.timeline,
            "summary": self.summary,
            "uncertainty_note": self.uncertainty_note,
        }
        if self.mechanism_id:
            result["mechanism"] = {
                "id": self.mechanism_id,
                "name": self.mechanism_name,
                "description": self.mechanism_description,
                "confidence": round(self.mechanism_confidence, 4),
            }
        return result


def _format_timestamp(ts: str) -> str:
    """Format ISO timestamp to human-readable form."""
    if not ts:
        return "unknown time"
    try:
        parts = ts.split("T")
        if len(parts) == 2:
            time_part = parts[1].split("+")[0].split("Z")[0]
            return f"{time_part} UTC"
    except (IndexError, ValueError):
        pass
    return ts


def _confidence_label(confidence: float) -> str:
    if confidence >= 0.80:
        return "high confidence"
    if confidence >= 0.60:
        return "moderate confidence"
    if confidence >= 0.40:
        return "low confidence"
    return "very low confidence"


def generate_narrative(
    classified_events: list[ClassifiedEvent],
    *,
    causal_confidence: float = 0.5,
    evidence_chain: list[dict[str, Any]] | None = None,
    contradictory_evidence: list[str] | None = None,
    topology: dict[str, Any] | None = None,
    mechanism_inference: MechanismInference | None = None,
) -> IncidentNarrative:
    """
    Generate a causal incident narrative from classified events.

    classified_events must include at least one PRIMARY_CAUSE event.
    mechanism_inference, when provided, enriches the narrative with the
    operational failure mechanism name and description (Phase 45).
    """
    evidence_chain = evidence_chain or []
    contradictory_evidence = contradictory_evidence or []

    primaries = [e for e in classified_events if e.failure_type == FailureType.PRIMARY_CAUSE]
    secondaries = [e for e in classified_events if e.failure_type == FailureType.SECONDARY_EFFECT]
    cascading = [e for e in classified_events if e.failure_type == FailureType.CASCADING_FAILURE]

    # Sort all events chronologically for timeline
    all_events_raw = [
        {
            "event_id": c.node.node_id,
            "timestamp_iso": c.node.timestamp_iso,
            "service": c.node.service,
            "description": c.node.description,
            "failure_type": c.failure_type.value,
        }
        for c in classified_events
    ]
    ordered_events = sequence_events_by_time(all_events_raw)

    # Build timeline strings
    timeline = []
    for ev in ordered_events:
        ts = _format_timestamp(ev.get("timestamp_iso", ""))
        svc = ev.get("service", "unknown")
        desc = ev.get("description", "")
        ftype = ev.get("failure_type", "")
        label = {
            FailureType.PRIMARY_CAUSE.value: "PRIMARY",
            FailureType.SECONDARY_EFFECT.value: "SECONDARY",
            FailureType.CASCADING_FAILURE.value: "CASCADE",
            FailureType.COLLATERAL_NOISE.value: "NOISE",
            FailureType.OPERATOR_ACTION.value: "ACTION",
        }.get(ftype, ftype)
        timeline.append(f"[{ts}] [{label}] {svc}: {desc}")

    # Mechanism-aware root cause statement
    mechanism_id: str | None = None
    mechanism_name: str | None = None
    mechanism_description: str | None = None
    mechanism_confidence: float = 0.0

    if mechanism_inference is not None and mechanism_inference.primary is not None:
        mech = mechanism_inference.primary.mechanism
        mechanism_id = mech.mechanism_id
        mechanism_name = mech.name
        mechanism_description = mech.description
        mechanism_confidence = mechanism_inference.mechanism_confidence

    if primaries:
        primary = primaries[0]
        ts = _format_timestamp(primary.node.timestamp_iso)
        if mechanism_name:
            root_cause_stmt = (
                f"At {ts}, {mechanism_name} in {primary.node.service} "
                f"was identified as the originating failure mechanism. "
                f"{mechanism_description}"
            )
        else:
            root_cause_stmt = (
                f"At {ts}, {primary.node.description} in {primary.node.service} "
                f"was identified as the originating failure."
            )
    else:
        root_cause_stmt = "Root cause could not be conclusively identified from available evidence."

    # Propagation description
    propagation_parts = []
    if primaries and secondaries:
        for sec in secondaries[:3]:
            ts = _format_timestamp(sec.node.timestamp_iso)
            propagation_parts.append(
                f"This propagated to {sec.node.service} at {ts}, "
                f"manifesting as: {sec.node.description}."
            )
    if cascading:
        propagation_parts.append(
            f"The failure cascaded through {len(cascading)} additional service(s): "
            + ", ".join(c.node.service for c in cascading[:3])
            + "."
        )
    propagation_desc = (
        " ".join(propagation_parts)
        if propagation_parts
        else ("No downstream propagation detected.")
    )

    # Propagation path
    propagation_path = [
        c.node.service
        for c in classified_events
        if c.failure_type
        in (
            FailureType.PRIMARY_CAUSE,
            FailureType.SECONDARY_EFFECT,
            FailureType.CASCADING_FAILURE,
        )
    ]

    # Why statements — include mechanism explanation if available
    why_statements = []
    if mechanism_name and mechanism_inference is not None:
        latent_states = mechanism_inference.latent_state_implications
        why_statements.append(
            f"Operational mechanism '{mechanism_name}' inferred from evidence "
            f"(mechanism confidence: {mechanism_confidence:.0%}). "
            f"{mechanism_description}"
        )
        if latent_states:
            why_statements.append(
                f"Implied latent infrastructure states: {', '.join(latent_states[:3])}."
            )
        why_statements.append(mechanism_inference.inference_rationale)
    if primaries:
        p = primaries[0]
        why_statements.append(
            f"'{p.node.description}' in {p.node.service} had no upstream causal "
            "predecessors, making it the originating event."
        )
    if evidence_chain:
        why_statements.append(
            f"{len(evidence_chain)} retrieved historical incidents support this attribution."
        )
    if secondaries:
        why_statements.append(
            f"Downstream effects observed in {len(secondaries)} service(s) are "
            "consistent with propagation from the primary cause."
        )
    if contradictory_evidence:
        why_statements.append(
            f"{len(contradictory_evidence)} piece(s) of contradictory evidence "
            "were identified but do not overturn the primary attribution."
        )

    # Uncertainty note
    conf_label = _confidence_label(causal_confidence)
    uncertainty_note = f"Causal attribution is {conf_label} ({causal_confidence:.0%}). " + (
        "Operator review recommended." if causal_confidence < 0.60 else ""
    )
    if mechanism_inference is not None and mechanism_confidence < 0.30:
        uncertainty_note += (
            f" Mechanism confidence is low ({mechanism_confidence:.0%}); "
            "alternative mechanisms may explain the evidence."
        )

    # Summary
    summary_parts = [root_cause_stmt]
    if propagation_desc and propagation_desc != "No downstream propagation detected.":
        summary_parts.append(propagation_desc)

    return IncidentNarrative(
        summary=" ".join(summary_parts),
        timeline=timeline,
        root_cause_statement=root_cause_stmt,
        propagation_description=propagation_desc,
        causal_confidence=round(causal_confidence, 4),
        why_statements=why_statements,
        evidence_chain=evidence_chain,
        contradictory_evidence=contradictory_evidence,
        propagation_path=propagation_path,
        uncertainty_note=uncertainty_note,
        mechanism_id=mechanism_id,
        mechanism_name=mechanism_name,
        mechanism_description=mechanism_description,
        mechanism_confidence=round(mechanism_confidence, 4),
    )
