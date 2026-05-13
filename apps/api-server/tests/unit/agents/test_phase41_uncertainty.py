"""
Phase 41 validation tests: Operational Uncertainty Modeling.

Proves:
  D. Missing telemetry — agents return structured UncertaintyIndicator with
     status=unavailable or status=partial rather than proceeding as if evidence
     is complete when it is not.
  E. Evidence provenance tracking — evidence items produced by
     normalize_agent_executions carry retrieval_timestamp, confidence, and
     uncertainty_status fields.
"""
from __future__ import annotations

from datetime import UTC, datetime

from agents.logs_agent.output_schema import ErrorSignature, LogsSummary
from agents.metrics_agent.output_schema import MetricAnomaly, MetricsSummary
from agents.deployment_agent.output_schema import DeploymentSummary, RecentChange
from agents.uncertainty import UncertaintyIndicator, infer_uncertainty_from_items
from evaluation.infra_mocks.mock_incident import MockAgentExecution
from agents.rootcause_agent.evidence_normalizer import normalize_agent_executions


# ─── D. Missing telemetry → structured uncertainty ────────────────────────────


def test_logs_summary_with_no_signatures_marks_unavailable() -> None:
    summary = LogsSummary(error_signatures=[], temporal_correlations=[])
    assert summary.evidence_quality.status == "unavailable"
    assert summary.evidence_quality.confidence == 0.0
    assert not summary.evidence_quality.is_actionable


def test_logs_summary_with_signatures_marks_present() -> None:
    sig = ErrorSignature(signature="TimeoutException", count=5, first_seen="14:00", sample="...")
    summary = LogsSummary(error_signatures=[sig])
    assert summary.evidence_quality.status == "present"


def test_metrics_summary_with_no_anomalies_marks_partial() -> None:
    summary = MetricsSummary(summary="no anomalies detected", anomalies=[])
    assert summary.evidence_quality.status == "partial"
    assert summary.evidence_quality.confidence < 1.0
    assert "insufficient telemetry" in summary.evidence_quality.reason.lower() or \
           summary.evidence_quality.status == "partial"


def test_metrics_summary_with_anomalies_marks_present() -> None:
    anomaly = MetricAnomaly(metric="latency_p99", observed="450ms", expected_range="<100ms", z_score=3.8)
    summary = MetricsSummary(summary="latency spike", anomalies=[anomaly])
    assert summary.evidence_quality.status == "present"


def test_deployment_summary_with_no_changes_marks_unavailable() -> None:
    summary = DeploymentSummary(recent_changes=[], correlation_with_incident="none")
    assert summary.evidence_quality.status == "unavailable"
    assert summary.evidence_quality.confidence == 0.0


def test_deployment_summary_with_all_missing_shas_marks_partial() -> None:
    change = RecentChange(
        deployment_id="dep-1",
        service="payment-api",
        version="1.2.3",
        time="2024-01-01T14:00:00Z",
        commit_sha="",
        commit_summary="Unknown change",
        risk_score=0.6,
    )
    summary = DeploymentSummary(recent_changes=[change], correlation_with_incident="possible")
    assert summary.evidence_quality.status == "partial"
    assert "provenance unverifiable" in summary.evidence_quality.reason


def test_deployment_summary_with_verified_sha_marks_present() -> None:
    change = RecentChange(
        deployment_id="dep-1",
        service="payment-api",
        version="1.2.3",
        time="2024-01-01T14:00:00Z",
        commit_sha="abc123def456",
        commit_author="alice",
        commit_summary="Bump dependency",
        risk_score=0.4,
    )
    summary = DeploymentSummary(recent_changes=[change], correlation_with_incident="likely")
    assert summary.evidence_quality.status == "present"


# ─── UncertaintyIndicator helpers ─────────────────────────────────────────────


def test_uncertainty_indicator_is_actionable_for_present_and_partial() -> None:
    assert UncertaintyIndicator.present().is_actionable is True
    assert UncertaintyIndicator.partial("low confidence", confidence=0.5).is_actionable is True


def test_uncertainty_indicator_is_not_actionable_for_unavailable() -> None:
    assert UncertaintyIndicator.unavailable("no data").is_actionable is False


def test_uncertainty_indicator_is_not_actionable_for_low_confidence_partial() -> None:
    assert UncertaintyIndicator.partial("very low confidence", confidence=0.2).is_actionable is False


def test_infer_uncertainty_returns_unavailable_for_empty_items() -> None:
    result = infer_uncertainty_from_items([])
    assert result.status == "unavailable"
    assert result.confidence == 0.0


def test_infer_uncertainty_returns_present_for_high_confidence_items() -> None:
    items = [
        {"uncertainty_status": "present", "confidence": 0.9},
        {"uncertainty_status": "present", "confidence": 0.8},
    ]
    result = infer_uncertainty_from_items(items)
    assert result.status == "present"
    assert result.confidence > 0.7


def test_infer_uncertainty_returns_partial_for_all_partial_items() -> None:
    items = [
        {"uncertainty_status": "partial", "confidence": 0.6},
        {"uncertainty_status": "partial", "confidence": 0.7},
    ]
    result = infer_uncertainty_from_items(items)
    assert result.status == "partial"


def test_infer_uncertainty_returns_conflicting_when_conflict_item_present() -> None:
    items = [
        {"uncertainty_status": "present", "confidence": 0.9},
        {"uncertainty_status": "conflicting", "confidence": 0.3},
    ]
    result = infer_uncertainty_from_items(items)
    assert result.status == "conflicting"


# ─── E. Evidence provenance tracking in normalizer ────────────────────────────


def test_normalize_agent_executions_adds_retrieval_timestamp_to_metrics() -> None:
    execution = MockAgentExecution(
        "metrics_agent",
        {
            "summary": "latency spike",
            "anomalies": [
                {"metric": "latency_p99", "observed": "450ms", "expected_range": "<100ms", "z_score": 3.8}
            ],
        },
    )
    items = normalize_agent_executions([execution])
    assert len(items) == 1
    assert "retrieval_timestamp" in items[0]
    ts = items[0]["retrieval_timestamp"]
    parsed = datetime.fromisoformat(ts)
    assert parsed.tzinfo is not None


def test_normalize_agent_executions_adds_confidence_to_metrics() -> None:
    execution = MockAgentExecution(
        "metrics_agent",
        {
            "summary": "high deviation",
            "anomalies": [
                {"metric": "latency_p99", "observed": "450ms", "expected_range": "<100ms",
                 "z_score": 3.8, "deviation_factor": 4.5}
            ],
        },
    )
    items = normalize_agent_executions([execution])
    assert items[0]["confidence"] > 0.5
    assert 0.0 <= items[0]["confidence"] <= 1.0


def test_normalize_agent_executions_marks_uncertainty_status_for_logs() -> None:
    execution = MockAgentExecution(
        "logs_agent",
        {
            "error_signatures": [
                {
                    "signature": "TimeoutException",
                    "count": 10,
                    "first_seen": "14:00:00",
                    "sample": "timeout",
                    "trace_ids": ["t1", "t2", "t3"],
                }
            ]
        },
    )
    items = normalize_agent_executions([execution])
    assert items[0]["uncertainty_status"] == "present"


def test_normalize_agent_executions_marks_partial_for_deployment_without_sha() -> None:
    execution = MockAgentExecution(
        "deployment_agent",
        {
            "recent_changes": [
                {
                    "deployment_id": "dep-1",
                    "service": "payment-api",
                    "version": "1.2.3",
                    "time": "2024-01-01T14:00:00Z",
                    "commit_sha": "",
                    "commit_summary": "Unknown change",
                    "risk_score": 0.5,
                }
            ]
        },
    )
    items = normalize_agent_executions([execution])
    assert items[0]["uncertainty_status"] == "partial"


def test_normalize_agent_executions_marks_present_for_deployment_with_sha() -> None:
    execution = MockAgentExecution(
        "deployment_agent",
        {
            "recent_changes": [
                {
                    "deployment_id": "dep-1",
                    "service": "payment-api",
                    "version": "1.2.3",
                    "time": "2024-01-01T14:00:00Z",
                    "commit_sha": "abc123def456",
                    "commit_author": "alice",
                    "commit_summary": "Bump dependency",
                    "risk_score": 0.4,
                }
            ]
        },
    )
    items = normalize_agent_executions([execution])
    assert items[0]["uncertainty_status"] == "present"
    assert items[0]["confidence"] > 0.5


def test_all_evidence_items_have_required_provenance_fields() -> None:
    metrics_exec = MockAgentExecution(
        "metrics_agent",
        {"summary": "ok", "anomalies": [
            {"metric": "cpu", "observed": "90%", "expected_range": "<80%", "z_score": 2.1}
        ]},
    )
    logs_exec = MockAgentExecution(
        "logs_agent",
        {"error_signatures": [
            {"signature": "OOMException", "count": 3, "first_seen": "15:00", "sample": "OOM", "trace_ids": []}
        ]},
    )
    deploy_exec = MockAgentExecution(
        "deployment_agent",
        {"recent_changes": [
            {"deployment_id": "d1", "service": "svc", "version": "1.0", "time": "now",
             "commit_sha": "abc", "commit_author": "bob", "commit_summary": "fix", "risk_score": 0.3}
        ]},
    )

    items = normalize_agent_executions([metrics_exec, logs_exec, deploy_exec])
    assert len(items) == 3

    for item in items:
        assert "retrieval_timestamp" in item, f"Missing retrieval_timestamp in {item['item_key']}"
        assert "confidence" in item, f"Missing confidence in {item['item_key']}"
        assert "uncertainty_status" in item, f"Missing uncertainty_status in {item['item_key']}"
        assert isinstance(item["confidence"], float)
        assert 0.0 <= item["confidence"] <= 1.0
