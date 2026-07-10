from __future__ import annotations

from evaluation.benchmark_suite import BenchmarkIncident, BenchmarkSuite
from evaluation.scorers.rootcause_scorer import (
    classify_failure_mode,
    detailed_score_root_cause,
)


def test_classify_failure_mode() -> None:
    # 1. generic_fallback
    assert classify_failure_mode("", "OOM") == "generic_fallback"
    assert classify_failure_mode("fallback option", "OOM") == "generic_fallback"

    # 2. temporal_confusion
    assert classify_failure_mode("CPU spike after database latency", "OOM") == "temporal_confusion"

    # 3. missing_evidence
    incident_no_telemetry = BenchmarkIncident(
        id="1",
        name="test-inc",
        version="1.0",
        category="memory_leak",
        description="test",
        alert_payload={},
        metrics_snapshot=[],
        logs_sample=[],
        mocked_tool_responses={},
        golden_classification="memory_pressure",
        golden_severity="medium",
        golden_root_cause="OOM",
        golden_remediation="reboot",
        golden_remediation_class="SAFE_AND_CORRECT",
        golden_expected_blast_radius_mean=10,
        golden_remediation_safe=True,
        golden_operator_action="APPROVE",
        expected_confidence_range=[0.5, 0.9],
        is_noisy_alert=False,
        is_false_positive=False,
        requires_escalation=False,
        risk_tier="MODERATE",
    )
    assert classify_failure_mode("OOM", "OOM", incident_no_telemetry) == "missing_evidence"

    # 4. pattern_mismatch
    incident_mismatch = BenchmarkIncident(
        id="2",
        name="test-inc-2",
        version="1.0",
        category="postgresql_failure",
        description="test",
        alert_payload={},
        metrics_snapshot=[{"metric": "db_lag", "observed": 10}],
        logs_sample=[{"message": "error"}],
        mocked_tool_responses={"router": {"pattern_hints": [{"pattern_id": "db_index_missing"}]}},
        golden_classification="database_failure",
        golden_severity="medium",
        golden_root_cause="OOM",
        golden_remediation="reboot",
        golden_remediation_class="SAFE_AND_CORRECT",
        golden_expected_blast_radius_mean=10,
        golden_remediation_safe=True,
        golden_operator_action="APPROVE",
        expected_confidence_range=[0.5, 0.9],
        is_noisy_alert=False,
        is_false_positive=False,
        requires_escalation=False,
        risk_tier="MODERATE",
    )
    assert (
        classify_failure_mode("wrong description", "OOM", incident_mismatch) == "pattern_mismatch"
    )

    # 5. default: wrong_evidence_weight
    incident_other = BenchmarkIncident(
        id="3",
        name="test-inc-3",
        version="1.0",
        category="postgresql_failure",
        description="test",
        alert_payload={},
        metrics_snapshot=[{"metric": "db_lag", "observed": 10}],
        logs_sample=[{"message": "error"}],
        mocked_tool_responses={},
        golden_classification="database_failure",
        golden_severity="medium",
        golden_root_cause="OOM",
        golden_remediation="reboot",
        golden_remediation_class="SAFE_AND_CORRECT",
        golden_expected_blast_radius_mean=10,
        golden_remediation_safe=True,
        golden_operator_action="APPROVE",
        expected_confidence_range=[0.5, 0.9],
        is_noisy_alert=False,
        is_false_positive=False,
        requires_escalation=False,
        risk_tier="MODERATE",
    )
    assert (
        classify_failure_mode("wrong description", "OOM", incident_other) == "wrong_evidence_weight"
    )


def test_detailed_score_root_cause() -> None:
    score, mode = detailed_score_root_cause("database failure", "database failure")
    assert score >= 0.6
    assert mode == "correct"

    score, mode = detailed_score_root_cause("", "database failure")
    assert score < 0.6
    assert mode == "generic_fallback"


def test_accuracy_by_category() -> None:
    inc = BenchmarkIncident(
        id="1",
        name="test-inc",
        version="1.0",
        category="memory_leak",
        description="test",
        alert_payload={},
        metrics_snapshot=[],
        logs_sample=[],
        mocked_tool_responses={},
        golden_classification="memory_pressure",
        golden_severity="medium",
        golden_root_cause="OOM",
        golden_remediation="reboot",
        golden_remediation_class="SAFE_AND_CORRECT",
        golden_expected_blast_radius_mean=10,
        golden_remediation_safe=True,
        golden_operator_action="APPROVE",
        expected_confidence_range=[0.5, 0.9],
        is_noisy_alert=False,
        is_false_positive=False,
        requires_escalation=False,
        risk_tier="MODERATE",
    )
    suite = BenchmarkSuite(
        suite_id="test",
        version="1.0",
        created="today",
        description="desc",
        total_incidents=1,
        categories=["memory_leak"],
        incidents=[inc],
    )
    results = [
        {
            "name": "test-inc",
            "rootcause_score_lexical": 0.8,
        }
    ]
    report = suite.accuracy_by_category(results)
    assert "memory_leak" in report
    assert report["memory_leak"]["total"] == 1
    assert report["memory_leak"]["correct"] == 1
    assert report["memory_leak"]["accuracy"] == 1.0


def test_failure_mode_breakdown() -> None:
    inc = BenchmarkIncident(
        id="1",
        name="test-inc",
        version="1.0",
        category="memory_leak",
        description="test",
        alert_payload={},
        metrics_snapshot=[],
        logs_sample=[],
        mocked_tool_responses={},
        golden_classification="memory_pressure",
        golden_severity="medium",
        golden_root_cause="OOM",
        golden_remediation="reboot",
        golden_remediation_class="SAFE_AND_CORRECT",
        golden_expected_blast_radius_mean=10,
        golden_remediation_safe=True,
        golden_operator_action="APPROVE",
        expected_confidence_range=[0.5, 0.9],
        is_noisy_alert=False,
        is_false_positive=False,
        requires_escalation=False,
        risk_tier="MODERATE",
    )
    suite = BenchmarkSuite(
        suite_id="test",
        version="1.0",
        created="today",
        description="desc",
        total_incidents=1,
        categories=["memory_leak"],
        incidents=[inc],
    )
    results = [
        {
            "name": "test-inc",
            "rootcause_score_lexical": 0.2,
            "predicted_root_cause": "fallback",
        }
    ]
    breakdown = suite.failure_mode_breakdown(results)
    assert breakdown["generic_fallback"] == 1
