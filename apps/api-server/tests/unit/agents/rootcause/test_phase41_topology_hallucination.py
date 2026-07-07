"""
Phase 41 topology-aware hallucination boundary tests.

Proves:
  B. Fabricated service detection — build_candidate_causes rejects patterns
     that reference services not registered in the topology, preventing the
     root cause agent from reasoning about infrastructure that does not exist.
"""

from __future__ import annotations

from agents.rootcause_agent.causal_graph import build_candidate_causes
from agents.rootcause_agent.evidence_builder import TimedEvent
from causality.validators.causal_validator import (
    HallucinationViolation,
    check_service_references,
    service_exists,
)
from orchestration.state.topology_schema import ServiceNode


def _make_topology() -> dict[str, ServiceNode]:
    return {
        "payment-api": ServiceNode(name="payment-api", depends_on=["order-service", "postgres"]),
        "order-service": ServiceNode(name="order-service", depends_on=["postgres"]),
        "postgres": ServiceNode(name="postgres", depends_on=[]),
    }


# ─── service_exists ───────────────────────────────────────────────────────────


def test_service_exists_returns_true_for_registered_service() -> None:
    topology = _make_topology()
    assert service_exists("payment-api", topology) is True
    assert service_exists("postgres", topology) is True


def test_service_exists_returns_false_for_unknown_service() -> None:
    topology = _make_topology()
    assert service_exists("ghost-service", topology) is False
    assert service_exists("", topology) is False


# ─── check_service_references ─────────────────────────────────────────────────


def test_check_service_references_returns_empty_for_valid_services() -> None:
    topology = _make_topology()
    violations = check_service_references(["payment-api", "postgres"], topology)
    assert violations == []


def test_check_service_references_returns_violation_for_hallucinated_service() -> None:
    topology = _make_topology()
    violations = check_service_references(["payment-api", "hallucinated-svc"], topology)
    assert len(violations) == 1
    assert isinstance(violations[0], HallucinationViolation)
    assert violations[0].service == "hallucinated-svc"
    assert "not found in topology" in violations[0].reason


def test_check_service_references_reports_all_unknown_services() -> None:
    topology = _make_topology()
    violations = check_service_references(["ghost-a", "ghost-b", "payment-api"], topology)
    assert len(violations) == 2
    names = {v.service for v in violations}
    assert names == {"ghost-a", "ghost-b"}


# ─── build_candidate_causes rejects hallucinated services ─────────────────────


def test_build_candidate_causes_rejects_pattern_with_nonexistent_cause_service() -> None:
    topology = _make_topology()
    events: list[TimedEvent] = []
    pattern_with_fake_cause = [
        {
            "pattern_id": "fake-pattern",
            "title": "Fake service degradation",
            "cause_service": "hallucinated-svc",
            "effect_service": "payment-api",
            "symptoms": ["timeout"],
            "match_score": 0.9,
        }
    ]

    candidates = build_candidate_causes(
        service="payment-api",
        events=events,
        topology_graph=topology,
        pattern_hints=pattern_with_fake_cause,
    )

    cause_services = {c.cause_service for c in candidates}
    assert (
        "hallucinated-svc" not in cause_services
    ), "build_candidate_causes accepted a pattern referencing a hallucinated cause service"


def test_build_candidate_causes_rejects_pattern_with_nonexistent_affected_service() -> None:
    topology = _make_topology()
    events: list[TimedEvent] = []
    pattern_with_fake_effect = [
        {
            "pattern_id": "fake-effect-pattern",
            "title": "Real cause fake effect",
            "cause_service": "payment-api",
            "effect_service": "ghost-downstream",
            "symptoms": ["timeout"],
            "match_score": 0.8,
        }
    ]

    candidates = build_candidate_causes(
        service="payment-api",
        events=events,
        topology_graph=topology,
        pattern_hints=pattern_with_fake_effect,
    )

    affected_services = {c.affected_service for c in candidates}
    assert (
        "ghost-downstream" not in affected_services
    ), "build_candidate_causes accepted a pattern referencing a hallucinated affected service"


def test_build_candidate_causes_accepts_valid_topology_pattern() -> None:
    topology = _make_topology()
    events: list[TimedEvent] = []
    valid_pattern = [
        {
            "pattern_id": "db-saturation",
            "title": "Database saturation propagating to payment-api",
            "cause_service": "postgres",
            "effect_service": "payment-api",
            "symptoms": ["connection refused", "timeout"],
            "match_score": 0.85,
        }
    ]

    candidates = build_candidate_causes(
        service="payment-api",
        events=events,
        topology_graph=topology,
        pattern_hints=valid_pattern,
    )

    candidate_ids = {c.pattern_id for c in candidates}
    assert (
        "db-saturation" in candidate_ids
    ), "build_candidate_causes rejected a valid topology pattern"


def test_build_candidate_causes_falls_back_to_unknown_degradation_when_all_patterns_rejected() -> (
    None
):
    topology = _make_topology()
    events: list[TimedEvent] = []
    all_fake_patterns = [
        {
            "pattern_id": "fake-1",
            "cause_service": "ghost-a",
            "effect_service": "ghost-b",
            "symptoms": ["error"],
            "match_score": 0.9,
        }
    ]

    candidates = build_candidate_causes(
        service="payment-api",
        events=events,
        topology_graph=topology,
        pattern_hints=all_fake_patterns,
    )

    # Falls back to the generic unknown_service_degradation candidate
    assert len(candidates) >= 1
    assert candidates[0].pattern_id == "unknown_service_degradation"


def test_build_candidate_causes_skips_topology_check_when_graph_is_empty() -> None:
    """When no topology is loaded, the guard is lifted to avoid blocking on missing config."""
    empty_topology: dict[str, ServiceNode] = {}
    events: list[TimedEvent] = []
    pattern = [
        {
            "pattern_id": "any-pattern",
            "cause_service": "some-service",
            "effect_service": "other-service",
            "symptoms": ["error"],
            "match_score": 0.7,
        }
    ]

    candidates = build_candidate_causes(
        service="some-service",
        events=events,
        topology_graph=empty_topology,
        pattern_hints=pattern,
    )

    assert any(
        c.pattern_id == "any-pattern" for c in candidates
    ), "build_candidate_causes rejected a pattern when topology is empty — should bypass guard"
