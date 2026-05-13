"""
Phase 43 incident narrative generation and explainability tests.

Proves:
  - generate_narrative produces IncidentNarrative with all required fields.
  - root_cause_statement mentions the primary cause service.
  - timeline entries are sorted chronologically.
  - propagation_path includes primary and secondary services.
  - why_statements list is non-empty for a grounded narrative.
  - to_explainability_dict includes all operator-facing keys.
  - uncertainty_note reflects confidence level.
  - No primary → root_cause_statement indicates insufficient evidence.
  - Contradictory evidence surfaced in narrative output.
  - Evidence chain count referenced in why_statements.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from causality.event_graph import (
    CausalNode,
    NodeType,
)
from causality.failure_classifier import (
    ClassifiedEvent,
    FailureType,
)
from causality.narrative_generator import IncidentNarrative, generate_narrative


def _ts(offset_seconds: float = 0.0) -> str:
    base = datetime(2024, 1, 1, 14, 0, 0, tzinfo=UTC)
    return (base + timedelta(seconds=offset_seconds)).isoformat()


def _make_classified(
    node_id: str,
    node_type: NodeType,
    service: str,
    ts_offset: float,
    failure_type: FailureType,
    causal_depth: int = 0,
) -> ClassifiedEvent:
    node = CausalNode(
        node_id=node_id,
        node_type=node_type,
        service=service,
        timestamp_iso=_ts(ts_offset),
        description=f"{failure_type.value.lower()} event in {service}",
    )
    return ClassifiedEvent(
        node=node,
        failure_type=failure_type,
        causal_depth=causal_depth,
        rationale="test classification",
    )


def _make_incident_classified() -> list[ClassifiedEvent]:
    """Standard cascade: database (primary) → payment-api (secondary)."""
    return [
        _make_classified(
            "DB", NodeType.METRIC_ANOMALY, "database", 0, FailureType.PRIMARY_CAUSE, 0
        ),
        _make_classified(
            "API", NodeType.METRIC_ANOMALY, "payment-api", 120, FailureType.SECONDARY_EFFECT, 1
        ),
    ]


# ─── IncidentNarrative structure ──────────────────────────────────────────────


def test_generate_narrative_returns_incident_narrative() -> None:
    classified = _make_incident_classified()
    narrative = generate_narrative(classified, causal_confidence=0.85)
    assert isinstance(narrative, IncidentNarrative)


def test_narrative_root_cause_mentions_primary_service() -> None:
    classified = _make_incident_classified()
    narrative = generate_narrative(classified, causal_confidence=0.85)
    assert "database" in narrative.root_cause_statement


def test_narrative_timeline_is_chronological() -> None:
    classified = [
        _make_classified(
            "LATE", NodeType.METRIC_ANOMALY, "api", 120, FailureType.SECONDARY_EFFECT, 1
        ),
        _make_classified("EARLY", NodeType.METRIC_ANOMALY, "db", 0, FailureType.PRIMARY_CAUSE, 0),
    ]
    narrative = generate_narrative(classified, causal_confidence=0.75)
    # Timeline should start with the earlier event
    assert "db" in narrative.timeline[0]
    assert "api" in narrative.timeline[-1]


def test_narrative_propagation_path_includes_services() -> None:
    classified = _make_incident_classified()
    narrative = generate_narrative(classified, causal_confidence=0.85)
    assert "database" in narrative.propagation_path
    assert "payment-api" in narrative.propagation_path


def test_narrative_why_statements_non_empty() -> None:
    classified = _make_incident_classified()
    narrative = generate_narrative(classified, causal_confidence=0.85)
    assert len(narrative.why_statements) > 0


def test_narrative_why_mentions_upstream_predecessors() -> None:
    classified = _make_incident_classified()
    narrative = generate_narrative(classified, causal_confidence=0.85)
    combined = " ".join(narrative.why_statements)
    assert "no upstream causal predecessors" in combined


def test_narrative_no_primary_indicates_insufficient_evidence() -> None:
    classified = [
        _make_classified("NOISY", NodeType.ALERT, "unrelated", 0, FailureType.COLLATERAL_NOISE, 0),
    ]
    narrative = generate_narrative(classified, causal_confidence=0.20)
    assert "could not be conclusively identified" in narrative.root_cause_statement


def test_narrative_contradictory_evidence_surfaced() -> None:
    classified = _make_incident_classified()
    narrative = generate_narrative(
        classified,
        causal_confidence=0.75,
        contradictory_evidence=["deployment occurred 10 minutes after anomaly onset"],
    )
    assert len(narrative.contradictory_evidence) == 1
    assert "deployment" in narrative.contradictory_evidence[0]
    combined_why = " ".join(narrative.why_statements)
    assert "contradictory" in combined_why


def test_narrative_evidence_chain_count_in_why() -> None:
    classified = _make_incident_classified()
    evidence = [
        {"incident_id": "INC-001", "similarity_score": 0.90},
        {"incident_id": "INC-002", "similarity_score": 0.85},
    ]
    narrative = generate_narrative(classified, causal_confidence=0.80, evidence_chain=evidence)
    combined_why = " ".join(narrative.why_statements)
    assert "2" in combined_why or "two" in combined_why.lower() or "historical" in combined_why


def test_narrative_uncertainty_note_reflects_confidence() -> None:
    classified = _make_incident_classified()
    high_conf = generate_narrative(classified, causal_confidence=0.90)
    low_conf = generate_narrative(classified, causal_confidence=0.30)
    assert "high confidence" in high_conf.uncertainty_note
    assert "very low confidence" in low_conf.uncertainty_note
    assert "Operator review" in low_conf.uncertainty_note


# ─── to_explainability_dict ───────────────────────────────────────────────────


def test_explainability_dict_has_required_keys() -> None:
    classified = _make_incident_classified()
    narrative = generate_narrative(classified, causal_confidence=0.75)
    d = narrative.to_explainability_dict()
    required = {
        "root_cause",
        "why",
        "evidence_chain",
        "causal_confidence",
        "contradictory_evidence",
        "propagation_path",
        "timeline",
        "summary",
    }
    assert required.issubset(set(d.keys()))


def test_explainability_dict_confidence_matches_input() -> None:
    classified = _make_incident_classified()
    narrative = generate_narrative(classified, causal_confidence=0.83)
    d = narrative.to_explainability_dict()
    assert abs(d["causal_confidence"] - 0.83) < 0.01


def test_explainability_dict_propagation_path_is_list() -> None:
    classified = _make_incident_classified()
    narrative = generate_narrative(classified, causal_confidence=0.75)
    d = narrative.to_explainability_dict()
    assert isinstance(d["propagation_path"], list)


def test_summary_is_non_empty_string() -> None:
    classified = _make_incident_classified()
    narrative = generate_narrative(classified, causal_confidence=0.75)
    assert isinstance(narrative.summary, str)
    assert len(narrative.summary) > 20
