"""Tests for PostExecutionValidator (Phase 46)."""

from __future__ import annotations

import pytest
from learning.post_execution import (
    ActualOutcome,
    PostExecutionValidator,
    PredictionRecord,
)


def _prediction(
    incident_id: str = "INC-001",
    blast: int = 10,
    risk: float = 0.70,
    resolution: float | None = 30.0,
    remediation: str = "scale_replicas",
    confidence: float = 0.80,
) -> PredictionRecord:
    return PredictionRecord(
        incident_id=incident_id,
        predicted_blast_radius=blast,
        predicted_risk_score=risk,
        predicted_resolution_minutes=resolution,
        recommended_remediation=remediation,
        ai_confidence=confidence,
    )


def _actual(
    incident_id: str = "INC-001",
    blast: int = 10,
    severity: str = "high",
    resolution: float | None = 30.0,
    remediation: str = "scale_replicas",
    success: bool = True,
) -> ActualOutcome:
    return ActualOutcome(
        incident_id=incident_id,
        actual_blast_radius=blast,
        actual_severity=severity,
        actual_resolution_minutes=resolution,
        executed_remediation=remediation,
        success=success,
    )


class TestPostExecutionValidator:
    def test_perfect_prediction_is_accurate(self):
        v = PostExecutionValidator()
        result = v.validate(_prediction(), _actual())
        assert result.prediction_accurate is True
        assert result.remediation_matched is True
        assert result.discrepancy_summary == "prediction accurate"

    def test_blast_radius_error_computed(self):
        v = PostExecutionValidator()
        result = v.validate(_prediction(blast=10), _actual(blast=20))
        assert result.blast_radius_error == pytest.approx(0.50, abs=0.01)

    def test_blast_radius_within_tolerance_is_accurate(self):
        v = PostExecutionValidator()
        result = v.validate(_prediction(blast=10), _actual(blast=12))
        assert result.blast_radius_error < 0.50

    def test_blast_radius_outside_tolerance_is_inaccurate(self):
        v = PostExecutionValidator()
        result = v.validate(_prediction(blast=1), _actual(blast=10))
        assert result.prediction_accurate is False

    def test_risk_score_error_against_high_severity(self):
        v = PostExecutionValidator()
        result = v.validate(_prediction(risk=0.75), _actual(severity="high"))
        # high → 0.75 numeric; risk=0.75; error ≈ 0.0
        assert result.risk_score_error == pytest.approx(0.0, abs=0.01)

    def test_risk_score_error_against_low_severity(self):
        v = PostExecutionValidator()
        result = v.validate(_prediction(risk=0.80), _actual(severity="low"))
        # low → 0.25 numeric; error = |0.80 - 0.25| = 0.55
        assert result.risk_score_error == pytest.approx(0.55, abs=0.01)

    def test_remediation_mismatch_detected(self):
        v = PostExecutionValidator()
        result = v.validate(
            _prediction(remediation="scale_replicas"),
            _actual(remediation="increase_pool_size"),
        )
        assert result.remediation_matched is False
        assert "remediation mismatch" in result.discrepancy_summary

    def test_high_confidence_failure_not_justified(self):
        v = PostExecutionValidator()
        result = v.validate(_prediction(confidence=0.90), _actual(success=False))
        assert result.confidence_was_justified is False

    def test_high_confidence_success_is_justified(self):
        v = PostExecutionValidator()
        result = v.validate(_prediction(confidence=0.90), _actual(success=True))
        assert result.confidence_was_justified is True

    def test_low_confidence_failure_is_justified(self):
        v = PostExecutionValidator()
        result = v.validate(_prediction(confidence=0.55), _actual(success=False))
        assert result.confidence_was_justified is True

    def test_summarize_empty(self):
        v = PostExecutionValidator()
        summary = v.summarize()
        assert summary.total_validated == 0
        assert summary.calibration_score == 0.5

    def test_summarize_all_accurate(self):
        v = PostExecutionValidator()
        for i in range(3):
            v.validate(
                _prediction(incident_id=f"INC-{i:03d}"),
                _actual(incident_id=f"INC-{i:03d}"),
            )
        summary = v.summarize()
        assert summary.accurate_count == 3
        assert summary.accuracy_rate == 1.0
        assert summary.remediation_match_rate == 1.0

    def test_summarize_calibration_score_blended(self):
        v = PostExecutionValidator()
        v.validate(_prediction(), _actual())
        v.validate(
            _prediction(incident_id="INC-002", blast=1),
            _actual(incident_id="INC-002", blast=100),
        )
        summary = v.summarize()
        assert 0.0 < summary.calibration_score < 1.0

    def test_inaccurate_results_filtered(self):
        v = PostExecutionValidator()
        v.validate(_prediction(), _actual())
        v.validate(
            _prediction(incident_id="INC-002", blast=1),
            _actual(incident_id="INC-002", blast=100),
        )
        inaccurate = v.inaccurate_results()
        assert len(inaccurate) == 1

    def test_resolution_error_computed(self):
        v = PostExecutionValidator()
        result = v.validate(_prediction(resolution=30.0), _actual(resolution=60.0))
        assert result.resolution_time_error == pytest.approx(0.50, abs=0.01)

    def test_resolution_error_none_when_no_prediction(self):
        v = PostExecutionValidator()
        result = v.validate(_prediction(resolution=None), _actual(resolution=30.0))
        assert result.resolution_time_error is None

    def test_zero_blast_radius_both_zero(self):
        v = PostExecutionValidator()
        result = v.validate(_prediction(blast=0), _actual(blast=0))
        assert result.blast_radius_error == 0.0

    def test_to_dict_keys(self):
        v = PostExecutionValidator()
        result = v.validate(_prediction(), _actual())
        d = result.to_dict()
        for key in [
            "incident_id", "blast_radius_error", "risk_score_error",
            "remediation_matched", "prediction_accurate", "confidence_was_justified",
            "discrepancy_summary",
        ]:
            assert key in d
