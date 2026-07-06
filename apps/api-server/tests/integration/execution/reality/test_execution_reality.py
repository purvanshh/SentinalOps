"""Tests for Phase 48 execution truth and remediation verification."""

from __future__ import annotations

from execution.reality.execution_truth import ExecutionRealityState, ExecutionTruthClassifier
from execution.reality.outcome_consistency import ConsistencyVerdict, OutcomeConsistencyChecker
from execution.reality.remediation_verifier import RemediationVerifier, VerificationVerdict
from execution.reality.rollback_truth import RollbackOutcome, RollbackTruthAnalyzer

# ---------------------------------------------------------------------------
# ExecutionTruthClassifier
# ---------------------------------------------------------------------------


def _snapshots(error_rates: list[float]) -> list[dict]:
    return [
        {"timestamp_iso": f"2026-05-14T10:{i:02d}:00Z", "error_rate": r}
        for i, r in enumerate(error_rates)
    ]


class TestExecutionTruthClassifier:
    def test_verified_success(self):
        clf = ExecutionTruthClassifier()
        rec = clf.classify("INC-1", "REM-1", _snapshots([0.30, 0.15, 0.03, 0.01]))
        assert rec.state == ExecutionRealityState.VERIFIED_SUCCESS
        assert rec.is_genuine_success

    def test_false_recovery(self):
        clf = ExecutionTruthClassifier()
        rec = clf.classify("INC-1", "REM-1", _snapshots([0.30, 0.02, 0.01, 0.40]))
        assert rec.state == ExecutionRealityState.FALSE_RECOVERY
        assert rec.is_deceptive

    def test_rollback_collapse_when_rate_rises(self):
        clf = ExecutionTruthClassifier()
        rec = clf.classify("INC-1", "REM-1", _snapshots([0.05, 0.20, 0.40, 0.50]))
        assert rec.state == ExecutionRealityState.ROLLBACK_COLLAPSE

    def test_hidden_degradation_slow_drift(self):
        clf = ExecutionTruthClassifier()
        rec = clf.classify("INC-1", "REM-1", _snapshots([0.05, 0.07, 0.09, 0.12]))
        assert rec.state == ExecutionRealityState.HIDDEN_DEGRADATION

    def test_temporary_recovery_oscillation(self):
        clf = ExecutionTruthClassifier()
        rec = clf.classify("INC-1", "REM-1", _snapshots([0.30, 0.10, 0.25, 0.08, 0.30]))
        assert rec.state in (
            ExecutionRealityState.TEMPORARY_RECOVERY,
            ExecutionRealityState.FALSE_RECOVERY,
        )

    def test_no_snapshots_partial_failure(self):
        clf = ExecutionTruthClassifier()
        rec = clf.classify("INC-1", "REM-1", [])
        assert rec.state == ExecutionRealityState.PARTIAL_FAILURE

    def test_to_dict(self):
        clf = ExecutionTruthClassifier()
        rec = clf.classify("INC-1", "REM-1", _snapshots([0.30, 0.01]))
        d = rec.to_dict()
        assert "state" in d
        assert "confidence_penalty" in d

    def test_confidence_penalty_zero_for_success(self):
        clf = ExecutionTruthClassifier()
        rec = clf.classify("INC-1", "REM-1", _snapshots([0.30, 0.01, 0.01]))
        assert rec.confidence_penalty == 0.0


# ---------------------------------------------------------------------------
# RemediationVerifier
# ---------------------------------------------------------------------------


def _snap(error_rate: float) -> dict:
    return {"error_rate": error_rate}


class TestRemediationVerifier:
    def test_confirmed_improvement(self):
        verifier = RemediationVerifier()
        result = verifier.verify(
            "REM-1",
            pre_snapshots=[_snap(0.30), _snap(0.35)],
            post_snapshots=[_snap(0.05), _snap(0.04)],
        )
        assert result.verdict == VerificationVerdict.CONFIRMED
        assert result.delta < 0

    def test_no_effect(self):
        verifier = RemediationVerifier()
        result = verifier.verify(
            "REM-1",
            pre_snapshots=[_snap(0.20)],
            post_snapshots=[_snap(0.20)],
        )
        assert result.verdict == VerificationVerdict.NO_EFFECT

    def test_side_effects_detected(self):
        verifier = RemediationVerifier()
        result = verifier.verify(
            "REM-1",
            pre_snapshots=[{"error_rate": 0.30, "latency": 0.10}],
            post_snapshots=[{"error_rate": 0.05, "latency": 0.50}],
            watched_metrics=["latency"],
        )
        assert result.verdict == VerificationVerdict.SIDE_EFFECTS_DETECTED

    def test_insufficient_data(self):
        verifier = RemediationVerifier()
        result = verifier.verify("REM-1", [], [])
        assert result.verdict == VerificationVerdict.INSUFFICIENT_DATA

    def test_to_dict(self):
        verifier = RemediationVerifier()
        result = verifier.verify("REM-1", [_snap(0.30)], [_snap(0.05)])
        d = result.to_dict()
        assert "verdict" in d and "delta" in d


# ---------------------------------------------------------------------------
# RollbackTruthAnalyzer
# ---------------------------------------------------------------------------


def _attempt(version: str, error_rate: float, components: list[str] | None = None) -> dict:
    return {"version": version, "error_rate": error_rate, "components": components or []}


class TestRollbackTruthAnalyzer:
    def test_successful_rollback(self):
        analyzer = RollbackTruthAnalyzer()
        rec = analyzer.analyze(
            "RB-1",
            [_attempt("v1.0", 0.30, ["api"]), _attempt("v0.9", 0.02, ["api"])],
            affected_components=["api"],
        )
        assert rec.outcome == RollbackOutcome.SUCCESSFUL

    def test_rollback_loop(self):
        analyzer = RollbackTruthAnalyzer()
        rec = analyzer.analyze(
            "RB-1",
            [
                _attempt("v1.0", 0.30),
                _attempt("v0.9", 0.25),
                _attempt("v1.0", 0.28),
            ],
        )
        assert rec.outcome == RollbackOutcome.ROLLBACK_LOOP

    def test_cascade_failure(self):
        analyzer = RollbackTruthAnalyzer()
        rec = analyzer.analyze(
            "RB-1",
            [_attempt("v1.0", 0.10, ["api"]), _attempt("v0.9", 0.50, ["api"])],
        )
        assert rec.outcome == RollbackOutcome.CASCADE_FAILURE

    def test_false_positive(self):
        analyzer = RollbackTruthAnalyzer()
        rec = analyzer.analyze("RB-1", [_attempt("v1.0", 0.01), _attempt("v0.9", 0.02)])
        assert rec.outcome == RollbackOutcome.FALSE_POSITIVE

    def test_partial_rollback_when_components_remain(self):
        analyzer = RollbackTruthAnalyzer()
        rec = analyzer.analyze(
            "RB-1",
            [_attempt("v0.9", 0.02, ["api"])],
            affected_components=["api", "db"],
        )
        assert rec.outcome == RollbackOutcome.PARTIAL_ROLLBACK
        assert "db" in rec.components_still_affected

    def test_empty_attempts_partial(self):
        analyzer = RollbackTruthAnalyzer()
        rec = analyzer.analyze("RB-1", [])
        assert rec.outcome == RollbackOutcome.PARTIAL_ROLLBACK

    def test_to_dict(self):
        analyzer = RollbackTruthAnalyzer()
        rec = analyzer.analyze("RB-1", [_attempt("v0.9", 0.01)])
        d = rec.to_dict()
        assert "outcome" in d


# ---------------------------------------------------------------------------
# OutcomeConsistencyChecker
# ---------------------------------------------------------------------------


def _truth(state: ExecutionRealityState) -> object:
    from execution.reality.execution_truth import ExecutionTruthRecord

    return ExecutionTruthRecord(
        incident_id="INC-1",
        remediation_id="REM-1",
        state=state,
        evidence=[],
        confidence_penalty=0.20,
    )


class TestOutcomeConsistencyChecker:
    def test_consistent_success(self):
        checker = OutcomeConsistencyChecker()
        report = checker.check("resolved", _truth(ExecutionRealityState.VERIFIED_SUCCESS))
        assert report.verdict == ConsistencyVerdict.CONSISTENT

    def test_declared_success_but_false_recovery(self):
        checker = OutcomeConsistencyChecker()
        report = checker.check("resolved", _truth(ExecutionRealityState.FALSE_RECOVERY))
        assert report.verdict == ConsistencyVerdict.DECLARED_SUCCESS_BUT_DEGRADED

    def test_operator_reject_after_success_inconsistent(self):
        checker = OutcomeConsistencyChecker()
        report = checker.check(
            "resolved",
            _truth(ExecutionRealityState.VERIFIED_SUCCESS),
            operator_overrides=["reject"],
        )
        assert report.verdict != ConsistencyVerdict.CONSISTENT

    def test_deceptive_state_masked_as_success(self):
        checker = OutcomeConsistencyChecker()
        report = checker.check("resolved", _truth(ExecutionRealityState.HIDDEN_DEGRADATION))
        assert report.verdict == ConsistencyVerdict.DECLARED_SUCCESS_BUT_DEGRADED
        assert len(report.inconsistencies) > 0

    def test_reliability_score_high_for_genuine_success(self):
        checker = OutcomeConsistencyChecker()
        report = checker.check("resolved", _truth(ExecutionRealityState.VERIFIED_SUCCESS))
        assert report.reliability_score >= 0.70

    def test_to_dict(self):
        checker = OutcomeConsistencyChecker()
        report = checker.check("resolved", _truth(ExecutionRealityState.VERIFIED_SUCCESS))
        d = report.to_dict()
        assert "verdict" in d and "reliability_score" in d
