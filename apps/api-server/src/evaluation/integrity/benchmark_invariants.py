"""Benchmark invariant checker — proves evaluation and production paths remain aligned."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class InvariantViolation:
    invariant_name: str
    description: str
    evidence: dict[str, Any]
    severity: str = "high"

    def to_dict(self) -> dict[str, Any]:
        return {
            "invariant_name": self.invariant_name,
            "description": self.description,
            "evidence": self.evidence,
            "severity": self.severity,
        }


@dataclass
class InvariantCheckResult:
    all_passed: bool
    violations: list[InvariantViolation]
    checks_run: int
    checks_passed: int
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "all_passed": self.all_passed,
            "violations": [v.to_dict() for v in self.violations],
            "checks_run": self.checks_run,
            "checks_passed": self.checks_passed,
            "summary": self.summary,
        }


class BenchmarkInvariantChecker:
    """Verify that the benchmark system respects structural integrity rules.

    These invariants cannot be validated by unit tests alone — they require
    checking cross-cutting properties across the evaluation pipeline.
    """

    def __init__(self) -> None:
        self._custom_checks: list[tuple[str, Callable[..., InvariantViolation | None]]] = []

    def register(self, name: str, check_fn: Callable[..., "InvariantViolation | None"]) -> None:
        self._custom_checks.append((name, check_fn))

    def run_all(self, context: dict[str, Any]) -> "InvariantCheckResult":
        violations: list[InvariantViolation] = []
        checks_run = 0

        for check_method in [
            self._check_scorer_never_sees_labels,
            self._check_confidence_bounds,
            self._check_attribution_requires_evidence,
            self._check_evaluation_uses_runtime_outputs,
            self._check_no_shortcut_paths,
        ]:
            checks_run += 1
            result = check_method(context)
            if result is not None:
                violations.append(result)

        for name, fn in self._custom_checks:
            checks_run += 1
            try:
                result = fn(context)
                if result is not None:
                    violations.append(result)
            except Exception as exc:
                violations.append(
                    InvariantViolation(
                        invariant_name=name,
                        description=f"Invariant check raised exception: {exc}",
                        evidence={"exception": str(exc)},
                        severity="medium",
                    )
                )

        checks_passed = checks_run - len(violations)
        return InvariantCheckResult(
            all_passed=len(violations) == 0,
            violations=violations,
            checks_run=checks_run,
            checks_passed=checks_passed,
            summary=self._summarize(violations, checks_run, checks_passed),
        )

    def _check_scorer_never_sees_labels(self, ctx: dict[str, Any]) -> InvariantViolation | None:
        scorer_inputs = ctx.get("scorer_inputs", [])
        for inp in scorer_inputs:
            if any(
                k in str(inp).lower() for k in ["golden", "true_label", "ground_truth"]
            ):
                return InvariantViolation(
                    invariant_name="scorer_never_sees_labels",
                    description="Scorer input contains golden label fields",
                    evidence={"sample": inp},
                )
        return None

    def _check_confidence_bounds(self, ctx: dict[str, Any]) -> InvariantViolation | None:
        predictions = ctx.get("predictions", [])
        violations = [
            p for p in predictions
            if not (0.0 <= float(p.get("confidence", 0.5)) <= 1.0)
        ]
        if violations:
            return InvariantViolation(
                invariant_name="confidence_in_unit_interval",
                description=f"{len(violations)} predictions have confidence outside [0,1]",
                evidence={"count": len(violations), "examples": violations[:3]},
            )
        return None

    def _check_attribution_requires_evidence(self, ctx: dict[str, Any]) -> InvariantViolation | None:
        predictions = ctx.get("predictions", [])
        bad = [
            p for p in predictions
            if p.get("attribution") is not None
            and float(p.get("confidence", 1.0)) < 0.20
            and not p.get("uncertainty_flagged", False)
        ]
        if bad:
            return InvariantViolation(
                invariant_name="attribution_requires_minimum_confidence",
                description=f"{len(bad)} predictions attribute below confidence floor 0.20",
                evidence={"count": len(bad), "examples": bad[:3]},
            )
        return None

    def _check_evaluation_uses_runtime_outputs(self, ctx: dict[str, Any]) -> InvariantViolation | None:
        if ctx.get("evaluation_uses_mock_outputs", False):
            return InvariantViolation(
                invariant_name="evaluation_uses_runtime_outputs",
                description="Evaluation is scoring mock outputs, not actual runtime outputs",
                evidence={"evaluation_uses_mock_outputs": True},
            )
        return None

    def _check_no_shortcut_paths(self, ctx: dict[str, Any]) -> InvariantViolation | None:
        if ctx.get("evaluation_only_code_path_active", False):
            return InvariantViolation(
                invariant_name="no_evaluation_only_shortcuts",
                description="Evaluation-only code path is active — results may not reflect production behavior",
                evidence={"evaluation_only_code_path_active": True},
            )
        return None

    def _summarize(self, violations: list[InvariantViolation], run: int, passed: int) -> str:
        if not violations:
            return f"All {run} invariant checks passed."
        names = [v.invariant_name for v in violations]
        return f"{passed}/{run} invariant checks passed. Violations: {', '.join(names)}."
