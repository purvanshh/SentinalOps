"""
Post-Execution Validator for SentinelOps Phase 46.

Compares AI predictions made before remediation execution against
what actually happened. Tracks:
  - Predicted vs. actual blast radius
  - Predicted vs. actual resolution time
  - Predicted risk score vs. actual incident severity
  - Whether the recommended remediation matched the one that actually worked

Produces ValidationResult records that feed into calibration tracking.

Design constraints:
  - Comparison is purely retrospective — never modifies past decisions.
  - All discrepancy scores are bounded to [0.0, 1.0].
  - Results are human-readable and operator-reviewable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_SEVERITY_NUMERIC = {
    "critical": 1.0,
    "high": 0.75,
    "medium": 0.50,
    "low": 0.25,
    "info": 0.10,
    "": 0.50,
}


@dataclass
class PredictionRecord:
    """AI predictions made before remediation execution."""

    incident_id: str
    predicted_blast_radius: int
    predicted_risk_score: float
    predicted_resolution_minutes: float | None
    recommended_remediation: str
    ai_confidence: float
    mechanism_id: str | None = None
    timestamp_iso: str = ""


@dataclass
class ActualOutcome:
    """What actually happened after remediation."""

    incident_id: str
    actual_blast_radius: int
    actual_severity: str
    actual_resolution_minutes: float | None
    executed_remediation: str
    success: bool
    required_rollback: bool = False
    timestamp_iso: str = ""


@dataclass
class ValidationResult:
    """Comparison of AI prediction vs. actual outcome."""

    incident_id: str
    blast_radius_error: float  # |predicted - actual| / max(actual, 1)
    risk_score_error: float    # |predicted_risk - severity_numeric|
    resolution_time_error: float | None  # |predicted_minutes - actual| / max(actual, 1)
    remediation_matched: bool
    prediction_accurate: bool  # overall: all errors within tolerance
    confidence_was_justified: bool  # high confidence + success
    discrepancy_summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "blast_radius_error": round(self.blast_radius_error, 4),
            "risk_score_error": round(self.risk_score_error, 4),
            "resolution_time_error": (
                round(self.resolution_time_error, 4)
                if self.resolution_time_error is not None
                else None
            ),
            "remediation_matched": self.remediation_matched,
            "prediction_accurate": self.prediction_accurate,
            "confidence_was_justified": self.confidence_was_justified,
            "discrepancy_summary": self.discrepancy_summary,
        }


@dataclass
class CalibrationSummary:
    """Aggregate calibration statistics over multiple validation results."""

    total_validated: int
    accurate_count: int
    accuracy_rate: float
    mean_blast_radius_error: float
    mean_risk_score_error: float
    mean_resolution_error: float | None
    remediation_match_rate: float
    unjustified_high_confidence_count: int
    calibration_score: float  # 0.0 = poorly calibrated, 1.0 = perfectly calibrated

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_validated": self.total_validated,
            "accurate_count": self.accurate_count,
            "accuracy_rate": round(self.accuracy_rate, 4),
            "mean_blast_radius_error": round(self.mean_blast_radius_error, 4),
            "mean_risk_score_error": round(self.mean_risk_score_error, 4),
            "mean_resolution_error": (
                round(self.mean_resolution_error, 4)
                if self.mean_resolution_error is not None
                else None
            ),
            "remediation_match_rate": round(self.remediation_match_rate, 4),
            "unjustified_high_confidence_count": self.unjustified_high_confidence_count,
            "calibration_score": round(self.calibration_score, 4),
        }


class PostExecutionValidator:
    """
    Compares AI predictions against actual execution outcomes.

    Produces ValidationResult and aggregated CalibrationSummary
    to detect systematic over- or under-confidence.
    """

    _BLAST_TOLERANCE = 0.50    # 50% relative error = within tolerance
    _RISK_TOLERANCE = 0.25     # 0.25 difference in risk score = within tolerance
    _RESOLUTION_TOLERANCE = 0.50  # 50% relative error = within tolerance

    def __init__(self) -> None:
        self._results: list[ValidationResult] = []

    def validate(
        self, prediction: PredictionRecord, actual: ActualOutcome
    ) -> ValidationResult:
        """Validate a single prediction against its actual outcome."""
        blast_err = self._blast_error(
            prediction.predicted_blast_radius, actual.actual_blast_radius
        )
        risk_err = self._risk_error(
            prediction.predicted_risk_score, actual.actual_severity
        )
        res_err = self._resolution_error(
            prediction.predicted_resolution_minutes, actual.actual_resolution_minutes
        )

        remediation_matched = (
            prediction.recommended_remediation.lower().strip()
            == actual.executed_remediation.lower().strip()
        )

        blast_ok = blast_err <= self._BLAST_TOLERANCE
        risk_ok = risk_err <= self._RISK_TOLERANCE
        resolution_ok = res_err is None or res_err <= self._RESOLUTION_TOLERANCE
        prediction_accurate = blast_ok and risk_ok and resolution_ok

        confidence_justified = not (
            prediction.ai_confidence >= 0.80 and not actual.success
        )

        discrepancy_parts = []
        if not blast_ok:
            discrepancy_parts.append(
                f"blast_radius off by {blast_err:.0%} "
                f"(predicted {prediction.predicted_blast_radius}, "
                f"actual {actual.actual_blast_radius})"
            )
        if not risk_ok:
            discrepancy_parts.append(
                f"risk_score error {risk_err:.2f} "
                f"(predicted {prediction.predicted_risk_score:.2f}, "
                f"actual_severity={actual.actual_severity})"
            )
        if not remediation_matched:
            discrepancy_parts.append(
                f"remediation mismatch: recommended '{prediction.recommended_remediation}', "
                f"executed '{actual.executed_remediation}'"
            )
        if not confidence_justified:
            discrepancy_parts.append(
                f"high confidence ({prediction.ai_confidence:.0%}) but remediation failed"
            )

        summary = "; ".join(discrepancy_parts) if discrepancy_parts else "prediction accurate"

        result = ValidationResult(
            incident_id=actual.incident_id,
            blast_radius_error=blast_err,
            risk_score_error=risk_err,
            resolution_time_error=res_err,
            remediation_matched=remediation_matched,
            prediction_accurate=prediction_accurate,
            confidence_was_justified=confidence_justified,
            discrepancy_summary=summary,
        )
        self._results.append(result)
        return result

    def all_results(self) -> list[ValidationResult]:
        return list(self._results)

    def summarize(self) -> CalibrationSummary:
        """Aggregate all validation results into a CalibrationSummary."""
        if not self._results:
            return CalibrationSummary(
                total_validated=0,
                accurate_count=0,
                accuracy_rate=0.0,
                mean_blast_radius_error=0.0,
                mean_risk_score_error=0.0,
                mean_resolution_error=None,
                remediation_match_rate=0.0,
                unjustified_high_confidence_count=0,
                calibration_score=0.5,
            )

        n = len(self._results)
        accurate = sum(1 for r in self._results if r.prediction_accurate)
        matched = sum(1 for r in self._results if r.remediation_matched)
        unjustified = sum(1 for r in self._results if not r.confidence_was_justified)

        mean_blast = sum(r.blast_radius_error for r in self._results) / n
        mean_risk = sum(r.risk_score_error for r in self._results) / n

        res_errors = [
            r.resolution_time_error for r in self._results if r.resolution_time_error is not None
        ]
        mean_res = sum(res_errors) / len(res_errors) if res_errors else None

        accuracy_rate = accurate / n
        match_rate = matched / n
        # Calibration score: blend of accuracy rate and remediation match rate
        calibration = 0.6 * accuracy_rate + 0.4 * match_rate

        return CalibrationSummary(
            total_validated=n,
            accurate_count=accurate,
            accuracy_rate=round(accuracy_rate, 4),
            mean_blast_radius_error=round(mean_blast, 4),
            mean_risk_score_error=round(mean_risk, 4),
            mean_resolution_error=round(mean_res, 4) if mean_res is not None else None,
            remediation_match_rate=round(match_rate, 4),
            unjustified_high_confidence_count=unjustified,
            calibration_score=round(calibration, 4),
        )

    def results_for_incident(self, incident_id: str) -> list[ValidationResult]:
        return [r for r in self._results if r.incident_id == incident_id]

    def inaccurate_results(self) -> list[ValidationResult]:
        return [r for r in self._results if not r.prediction_accurate]

    # ------------------------------------------------------------------
    # Internal error calculators
    # ------------------------------------------------------------------

    @staticmethod
    def _blast_error(predicted: int, actual: int) -> float:
        if actual == 0 and predicted == 0:
            return 0.0
        denom = max(actual, 1)
        return round(min(1.0, abs(predicted - actual) / denom), 4)

    @staticmethod
    def _risk_error(predicted_risk: float, actual_severity: str) -> float:
        actual_numeric = _SEVERITY_NUMERIC.get(actual_severity.lower(), 0.50)
        return round(min(1.0, abs(predicted_risk - actual_numeric)), 4)

    @staticmethod
    def _resolution_error(
        predicted_minutes: float | None, actual_minutes: float | None
    ) -> float | None:
        if predicted_minutes is None or actual_minutes is None:
            return None
        if actual_minutes == 0 and predicted_minutes == 0:
            return 0.0
        denom = max(actual_minutes, 1.0)
        return round(min(1.0, abs(predicted_minutes - actual_minutes) / denom), 4)
