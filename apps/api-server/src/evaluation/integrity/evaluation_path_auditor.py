"""Evaluation path auditor — verifies production and evaluation logic paths are aligned."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class PathAuditReport:
    production_path_verified: bool
    evaluation_path_verified: bool
    paths_aligned: bool
    divergence_points: list[str]
    synthetic_inflation_risk: str  # "none", "low", "medium", "high"
    audit_notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "production_path_verified": self.production_path_verified,
            "evaluation_path_verified": self.evaluation_path_verified,
            "paths_aligned": self.paths_aligned,
            "divergence_points": self.divergence_points,
            "synthetic_inflation_risk": self.synthetic_inflation_risk,
            "audit_notes": self.audit_notes,
        }


class EvaluationPathAuditor:
    """Verify that evaluation pipeline logic matches production pipeline logic.

    The primary risk is evaluation-time shortcuts that produce better scores
    than would be achieved in production — benchmark theater.

    Checks:
    1. Same confidence calibration is used
    2. Same uncertainty thresholds are applied
    3. No evaluation-only data cleaning is applied
    4. Scorer receives only data available at production runtime
    """

    def audit(self, audit_context: dict[str, Any]) -> PathAuditReport:
        divergence: list[str] = []
        notes: list[str] = []

        prod_verified = self._verify_production_path(audit_context, divergence, notes)
        eval_verified = self._verify_evaluation_path(audit_context, divergence, notes)
        aligned = prod_verified and eval_verified and len(divergence) == 0

        inflation_risk = self._assess_inflation_risk(audit_context, divergence)

        return PathAuditReport(
            production_path_verified=prod_verified,
            evaluation_path_verified=eval_verified,
            paths_aligned=aligned,
            divergence_points=divergence,
            synthetic_inflation_risk=inflation_risk,
            audit_notes=notes,
        )

    def _verify_production_path(
        self, ctx: dict[str, Any], divergence: list[str], notes: list[str]
    ) -> bool:
        ok = True
        if not ctx.get("production_confidence_calibrator"):
            divergence.append("production_path_missing_confidence_calibration")
            ok = False
        if not ctx.get("production_uncertainty_handler"):
            divergence.append("production_path_missing_uncertainty_handler")
            ok = False
        if ctx.get("production_path_uses_golden_data"):
            divergence.append("production_path_should_not_use_golden_data")
            ok = False
        if ok:
            notes.append("Production path verified: calibration and uncertainty handling present.")
        return ok

    def _verify_evaluation_path(
        self, ctx: dict[str, Any], divergence: list[str], notes: list[str]
    ) -> bool:
        ok = True
        if ctx.get("evaluation_applies_extra_cleaning"):
            divergence.append("evaluation_applies_cleaning_not_in_production")
            ok = False
        if ctx.get("evaluation_uses_future_data"):
            divergence.append("evaluation_uses_data_not_available_at_inference_time")
            ok = False
        if ctx.get("evaluation_disables_uncertainty"):
            divergence.append("evaluation_disables_uncertainty_checks")
            ok = False
        if ok:
            notes.append("Evaluation path verified: no unfair advantages detected.")
        return ok

    def _assess_inflation_risk(self, ctx: dict[str, Any], divergence: list[str]) -> str:
        risk_factors = [
            ctx.get("evaluation_applies_extra_cleaning", False),
            ctx.get("evaluation_uses_future_data", False),
            ctx.get("evaluation_disables_uncertainty", False),
            ctx.get("synthetic_dataset_only", False),
            len(divergence) > 2,
        ]
        count = sum(1 for r in risk_factors if r)
        if count == 0:
            return "none"
        if count == 1:
            return "low"
        if count == 2:
            return "medium"
        return "high"
