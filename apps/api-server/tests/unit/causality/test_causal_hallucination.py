"""
Phase 43 causal hallucination detection tests.

Validates all five detection scenarios:
  D. Topology violation: hallucinated dependency chain rejected.
  E. Temporal contradiction: cause after effect flagged.
  A. Deployment after incident: deployment post-dating anomaly flagged.
  Alert storm: collateral alerts not attributed to causal service.

Also proves:
  - run_hallucination_detection aggregates all violation types.
  - HallucinationReport.is_clean reflects critical vs warning severity.
  - Suppressed candidates list includes all critical violators.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from causality.hallucination_detector import (
    CausalHallucination,
    HallucinationReport,
    HallucinationType,
    detect_alert_storm_misattribution,
    detect_deployment_misattribution,
    detect_temporal_contradictions,
    detect_topology_violations,
    run_hallucination_detection,
)


def _ts(offset_seconds: float = 0.0) -> str:
    base = datetime(2024, 1, 1, 14, 0, 0, tzinfo=UTC)
    return (base + timedelta(seconds=offset_seconds)).isoformat()


# ─── Scenario D: topology violation ──────────────────────────────────────────


def test_topology_violation_when_no_path_exists() -> None:
    claims = [
        {
            "cause_id": "unrelated-svc",
            "cause_service": "unrelated-service",
            "effect_id": "payment-api",
            "effect_service": "payment-api",
        }
    ]
    topology = {"dependencies": {"database": ["payment-api"]}}
    violations = detect_topology_violations(claims, topology)
    assert len(violations) == 1
    assert violations[0].violation_type == HallucinationType.TOPOLOGY_VIOLATION
    assert violations[0].severity == "critical"


def test_topology_no_violation_when_path_exists() -> None:
    claims = [
        {
            "cause_id": "db",
            "cause_service": "database",
            "effect_id": "api",
            "effect_service": "payment-api",
        }
    ]
    topology = {"dependencies": {"database": ["payment-api"]}}
    violations = detect_topology_violations(claims, topology)
    assert violations == []


def test_topology_no_violation_same_service() -> None:
    claims = [
        {
            "cause_id": "api",
            "cause_service": "payment-api",
            "effect_id": "api-2",
            "effect_service": "payment-api",
        }
    ]
    topology = {"dependencies": {}}
    violations = detect_topology_violations(claims, topology)
    assert violations == []


def test_topology_violation_evidence_mentions_services() -> None:
    claims = [
        {
            "cause_id": "ghost",
            "cause_service": "ghost-service",
            "effect_id": "api",
            "effect_service": "real-api",
        }
    ]
    topology = {"dependencies": {"database": ["real-api"]}}
    violations = detect_topology_violations(claims, topology)
    assert "ghost-service" in violations[0].evidence
    assert "real-api" in violations[0].evidence


# ─── Scenario E: temporal contradiction ──────────────────────────────────────


def test_temporal_contradiction_cause_after_effect() -> None:
    claims = [
        {
            "cause_id": "late-event",
            "cause_timestamp_iso": _ts(300),
            "effect_id": "early-anomaly",
            "effect_timestamp_iso": _ts(0),
        }
    ]
    violations = detect_temporal_contradictions(claims)
    assert len(violations) == 1
    assert violations[0].violation_type == HallucinationType.TEMPORAL_CONTRADICTION
    assert "AFTER" in violations[0].evidence


def test_temporal_no_contradiction_cause_before_effect() -> None:
    claims = [
        {
            "cause_id": "early",
            "cause_timestamp_iso": _ts(0),
            "effect_id": "late",
            "effect_timestamp_iso": _ts(300),
        }
    ]
    violations = detect_temporal_contradictions(claims)
    assert violations == []


def test_temporal_no_contradiction_missing_timestamps() -> None:
    claims = [{"cause_id": "a", "effect_id": "b"}]
    violations = detect_temporal_contradictions(claims)
    assert violations == []


# ─── Scenario A: deployment after incident ────────────────────────────────────


def test_deployment_after_incident_flagged() -> None:
    deployments = [{"id": "deploy-1", "timestamp_iso": _ts(300), "service": "payment-api"}]
    violations = detect_deployment_misattribution(deployments, _ts(0))
    assert len(violations) == 1
    assert violations[0].violation_type == HallucinationType.DEPLOYMENT_AFTER_INCIDENT
    assert violations[0].severity == "critical"


def test_deployment_before_incident_not_flagged() -> None:
    deployments = [{"id": "deploy-1", "timestamp_iso": _ts(0), "service": "payment-api"}]
    violations = detect_deployment_misattribution(deployments, _ts(300))
    assert violations == []


def test_deployment_evidence_mentions_timing() -> None:
    deployments = [{"id": "deploy-1", "timestamp_iso": _ts(120), "service": "api"}]
    violations = detect_deployment_misattribution(deployments, _ts(0))
    assert "120" in violations[0].evidence
    assert "cannot be the root cause" in violations[0].evidence


# ─── Alert storm misattribution ───────────────────────────────────────────────


def test_alert_storm_unconnected_service_is_warning() -> None:
    alerts = [
        {
            "id": "alert-1",
            "service": "unrelated-service",
            "attributed_to": "database",
        }
    ]
    topology = {"dependencies": {"database": ["payment-api"]}}
    violations = detect_alert_storm_misattribution(alerts, "database", topology)
    assert len(violations) == 1
    assert violations[0].severity == "warning"
    assert violations[0].violation_type == HallucinationType.ALERT_STORM_MISATTRIBUTION


def test_alert_storm_connected_service_no_violation() -> None:
    alerts = [
        {
            "id": "alert-1",
            "service": "payment-api",
            "attributed_to": "database",
        }
    ]
    topology = {"dependencies": {"database": ["payment-api"]}}
    violations = detect_alert_storm_misattribution(alerts, "database", topology)
    assert violations == []


# ─── run_hallucination_detection ──────────────────────────────────────────────


def test_run_detection_aggregates_all_violations() -> None:
    claims = [
        {
            "cause_id": "ghost",
            "cause_service": "ghost-service",
            "cause_timestamp_iso": _ts(500),
            "effect_id": "api",
            "effect_service": "payment-api",
            "effect_timestamp_iso": _ts(0),
        }
    ]
    topology = {"dependencies": {"database": ["payment-api"]}}
    report = run_hallucination_detection(
        claims,
        topology=topology,
    )
    assert len(report.violations) >= 1
    assert not report.is_clean


def test_run_detection_suppresses_critical_violators() -> None:
    deployments = [{"id": "deploy-1", "timestamp_iso": _ts(300), "service": "api"}]
    report = run_hallucination_detection(
        [],
        deployment_events=deployments,
        incident_onset_timestamp=_ts(0),
    )
    assert "deploy-1" in report.suppressed_candidates


def test_run_detection_clean_report_when_no_violations() -> None:
    claims = [
        {
            "cause_id": "db",
            "cause_service": "database",
            "cause_timestamp_iso": _ts(0),
            "effect_id": "api",
            "effect_service": "payment-api",
            "effect_timestamp_iso": _ts(120),
        }
    ]
    topology = {"dependencies": {"database": ["payment-api"]}}
    report = run_hallucination_detection(claims, topology=topology)
    assert report.is_clean is True
    assert report.critical_count == 0


def test_hallucination_report_counts_severities() -> None:
    report = HallucinationReport()
    report.violations.append(
        CausalHallucination(
            violation_type=HallucinationType.TOPOLOGY_VIOLATION,
            claimed_cause_id="a",
            claimed_effect_id="b",
            evidence="test",
            severity="critical",
        )
    )
    report.violations.append(
        CausalHallucination(
            violation_type=HallucinationType.ALERT_STORM_MISATTRIBUTION,
            claimed_cause_id="c",
            claimed_effect_id="d",
            evidence="test",
            severity="warning",
        )
    )
    assert report.critical_count == 1
    assert report.warning_count == 1
