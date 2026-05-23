"""
Tests for Phase 49 explainability quality scoring modules:
  - ExplainabilityQualityAnalyzer  (explainability_quality.py)
  - RationaleValidator             (rationale_validator.py)
  - NarrativeConsistencyChecker    (narrative_consistency.py)
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

import pytest
from operators.workflow.explainability_quality import (
    ExplainabilityQualityAnalyzer,
    ExplainabilityScore,
)
from operators.workflow.narrative_consistency import (
    NarrativeConsistencyChecker,
    NarrativeConsistencyReport,
)
from operators.workflow.rationale_validator import (
    RationaleIssue,
    RationaleValidationResult,
    RationaleValidator,
)

# ===========================================================================
# Fixtures / helpers
# ===========================================================================


def _make_analyzer() -> ExplainabilityQualityAnalyzer:
    return ExplainabilityQualityAnalyzer()


def _make_validator() -> RationaleValidator:
    return RationaleValidator()


def _make_checker() -> NarrativeConsistencyChecker:
    return NarrativeConsistencyChecker()


# ===========================================================================
# ExplainabilityQualityAnalyzer
# ===========================================================================


class TestExplainabilityQualityAnalyzer:
    # ---- Overall score computation ----------------------------------------

    def test_returns_explainability_score_dataclass(self) -> None:
        analyzer = _make_analyzer()
        result = analyzer.score(
            incident_id="inc-001",
            narrative="The service degraded because of high memory usage.",
            evidence_refs=["ref-1"],
            confidence=0.70,
            uncertainty_flags=["memory metrics may be delayed"],
            contradictions=[],
        )
        assert isinstance(result, ExplainabilityScore)
        assert result.incident_id == "inc-001"

    def test_overall_score_is_weighted_average(self) -> None:
        """Overall = 0.25*t + 0.20*h + 0.15*r + 0.15*ca + 0.15*cs + 0.10*rc."""
        analyzer = _make_analyzer()
        result = analyzer.score(
            incident_id="inc-002",
            narrative="Service crashed because of OOMKill.",
            evidence_refs=["ref-a", "ref-b"],
            confidence=0.65,
            uncertainty_flags=["metrics incomplete"],
            contradictions=["memory vs cpu disagree"],
        )
        expected = (
            0.25 * result.traceability_score
            + 0.20 * result.honesty_score
            + 0.15 * result.readability_score
            + 0.15 * result.contradiction_awareness
            + 0.15 * result.causal_specificity
            + 0.10 * result.rationale_completeness
        )
        assert result.overall_explainability_score == pytest.approx(expected, abs=1e-4)

    def test_all_scores_bounded_0_to_1(self) -> None:
        analyzer = _make_analyzer()
        result = analyzer.score(
            incident_id="inc-003",
            narrative="Cascading failure caused by thundering herd. CPU throttling detected. "
            "Backpressure increased due to circuit breaker tripping. "
            "P99 latency spike caused by OOMKill. MTTR exceeded SLA.",
            evidence_refs=[],
            confidence=0.99,
            uncertainty_flags=[],
            contradictions=[],
        )
        for field_name in [
            "traceability_score",
            "honesty_score",
            "readability_score",
            "contradiction_awareness",
            "causal_specificity",
            "rationale_completeness",
            "jargon_density",
            "overall_explainability_score",
        ]:
            value = getattr(result, field_name)
            assert 0.0 <= value <= 1.0, f"{field_name}={value} out of [0, 1]"

    def test_perfect_narrative_scores_high(self) -> None:
        """A well-cited, low-jargon, uncertainty-acknowledged narrative should score high."""
        analyzer = _make_analyzer()
        result = analyzer.score(
            incident_id="inc-004",
            narrative=(
                "The payment service degraded because of a database connection pool exhaustion "
                "(ref-1). This was caused by an abnormal spike in transaction volume (ref-2). "
                "We are uncertain whether the upstream cache was also a factor."
            ),
            evidence_refs=["ref-1", "ref-2"],
            confidence=0.68,
            uncertainty_flags=["cache contribution unclear"],
            contradictions=[],
        )
        assert result.overall_explainability_score >= 0.60

    def test_empty_narrative_does_not_crash(self) -> None:
        analyzer = _make_analyzer()
        result = analyzer.score(
            incident_id="inc-005",
            narrative="",
            evidence_refs=[],
            confidence=0.50,
            uncertainty_flags=[],
            contradictions=[],
        )
        assert isinstance(result, ExplainabilityScore)
        assert result.jargon_density == 0.0

    # ---- Jargon detection -------------------------------------------------

    def test_jargon_density_zero_for_plain_language(self) -> None:
        analyzer = _make_analyzer()
        result = analyzer.score(
            incident_id="inc-j1",
            narrative="The service restarted and traffic returned to normal levels.",
            evidence_refs=[],
            confidence=0.50,
            uncertainty_flags=[],
            contradictions=[],
        )
        assert result.jargon_density == 0.0

    def test_jargon_density_single_term(self) -> None:
        """Narrative with exactly one jargon token among many plain tokens."""
        analyzer = _make_analyzer()
        # "oom" is 1 jargon token; narrative has ~10 tokens total
        narrative = "The service went down due to oom out of all the services deployed."
        result = analyzer.score(
            incident_id="inc-j2",
            narrative=narrative,
            evidence_refs=[],
            confidence=0.50,
            uncertainty_flags=[],
            contradictions=[],
        )
        assert result.jargon_density > 0.0
        assert result.jargon_density < 0.5  # not majority jargon

    def test_jargon_density_multi_word_term(self) -> None:
        """Multi-word jargon terms are matched and counted by their word count."""
        analyzer = _make_analyzer()
        # "latency spike" = 2 jargon tokens; narrative ~6 tokens
        narrative = "We observed a latency spike in production today."
        result = analyzer.score(
            incident_id="inc-j3",
            narrative=narrative,
            evidence_refs=[],
            confidence=0.50,
            uncertainty_flags=[],
            contradictions=[],
        )
        assert result.jargon_density > 0.0

    def test_jargon_density_high_jargon_penalises_readability(self) -> None:
        """High jargon density should drive readability score down."""
        analyzer = _make_analyzer()
        heavy = (
            "mttr p99 oom oomkill cpu throttling backpressure circuit breaker "
            "thundering herd cascading failure latency spike"
        )
        light = "The service had elevated error rates during the incident window."
        result_heavy = analyzer.score(
            incident_id="inc-j4a",
            narrative=heavy,
            evidence_refs=[],
            confidence=0.50,
            uncertainty_flags=[],
            contradictions=[],
        )
        result_light = analyzer.score(
            incident_id="inc-j4b",
            narrative=light,
            evidence_refs=[],
            confidence=0.50,
            uncertainty_flags=[],
            contradictions=[],
        )
        assert result_heavy.readability_score < result_light.readability_score

    # ---- Unsupported claims -----------------------------------------------

    def test_unsupported_claims_zero_when_evidence_covers_causal_sentence(self) -> None:
        analyzer = _make_analyzer()
        result = analyzer.score(
            incident_id="inc-u1",
            narrative="The API failed because ref-1 showed connection timeout.",
            evidence_refs=["ref-1"],
            confidence=0.70,
            uncertainty_flags=[],
            contradictions=[],
        )
        assert result.unsupported_claims == 0

    def test_unsupported_claims_counted_without_evidence(self) -> None:
        analyzer = _make_analyzer()
        result = analyzer.score(
            incident_id="inc-u2",
            narrative=(
                "The API failed because of high CPU load. "
                "The database crashed caused by disk I/O saturation."
            ),
            evidence_refs=[],
            confidence=0.70,
            uncertainty_flags=[],
            contradictions=[],
        )
        assert result.unsupported_claims >= 2

    def test_non_causal_sentences_not_counted_as_unsupported(self) -> None:
        analyzer = _make_analyzer()
        result = analyzer.score(
            incident_id="inc-u3",
            narrative="The service had elevated error rates. Traffic was above normal.",
            evidence_refs=[],
            confidence=0.50,
            uncertainty_flags=[],
            contradictions=[],
        )
        # No causal language → no unsupported claims
        assert result.unsupported_claims == 0

    def test_unsupported_claims_is_non_negative_integer(self) -> None:
        analyzer = _make_analyzer()
        result = analyzer.score(
            incident_id="inc-u4",
            narrative="Something happened because of unknown reasons.",
            evidence_refs=[],
            confidence=0.50,
            uncertainty_flags=[],
            contradictions=[],
        )
        assert isinstance(result.unsupported_claims, int)
        assert result.unsupported_claims >= 0

    # ---- Honesty score ----------------------------------------------------

    def test_high_confidence_no_flags_lowers_honesty(self) -> None:
        analyzer = _make_analyzer()
        result_honest = analyzer.score(
            incident_id="inc-h1",
            narrative="Service degraded.",
            evidence_refs=[],
            confidence=0.95,
            uncertainty_flags=["some signals missing"],
            contradictions=[],
        )
        result_overconfident = analyzer.score(
            incident_id="inc-h2",
            narrative="Service degraded.",
            evidence_refs=[],
            confidence=0.95,
            uncertainty_flags=[],
            contradictions=[],
        )
        assert result_honest.honesty_score > result_overconfident.honesty_score

    # ---- Contradiction awareness ------------------------------------------

    def test_acknowledged_contradictions_raise_awareness_score(self) -> None:
        analyzer = _make_analyzer()
        result = analyzer.score(
            incident_id="inc-c1",
            narrative="Service metrics conflict between stable and degrading readings.",
            evidence_refs=[],
            confidence=0.60,
            uncertainty_flags=[],
            contradictions=["CPU reports stable, memory reports degrading"],
        )
        # Having acknowledged contradictions should score >= 0.40
        assert result.contradiction_awareness >= 0.40

    def test_unacknowledged_contradiction_in_narrative_reduces_score(self) -> None:
        analyzer = _make_analyzer()
        result = analyzer.score(
            incident_id="inc-c2",
            narrative="The system is stable and the system is degrading simultaneously.",
            evidence_refs=[],
            confidence=0.60,
            uncertainty_flags=[],
            contradictions=[],  # not acknowledged
        )
        # Implicit contradiction without acknowledgment should score below 1.0
        assert result.contradiction_awareness < 1.0


# ===========================================================================
# RationaleValidator
# ===========================================================================


class TestRationaleValidator:
    # ---- Passing case -----------------------------------------------------

    def test_clean_rationale_passes(self) -> None:
        validator = _make_validator()
        result = validator.validate(
            incident_id="inc-v1",
            narrative=(
                "The database connection pool was exhausted because of a traffic surge. "
                "Two evidence references support this conclusion."
            ),
            confidence=0.72,
            evidence_refs=["ref-1", "ref-2"],
            escalation_reason=None,
        )
        assert result.passed is True
        assert result.high_severity_count == 0

    def test_result_is_correct_dataclass(self) -> None:
        validator = _make_validator()
        result = validator.validate(
            incident_id="inc-v2",
            narrative="Service degraded.",
            confidence=0.50,
            evidence_refs=["ref-1"],
            escalation_reason=None,
        )
        assert isinstance(result, RationaleValidationResult)
        assert result.incident_id == "inc-v2"
        assert result.total_violations == len(result.violations)

    # ---- UNSUPPORTED_CERTAINTY --------------------------------------------

    def test_unsupported_certainty_high_confidence_no_evidence(self) -> None:
        validator = _make_validator()
        result = validator.validate(
            incident_id="inc-v3",
            narrative="The root cause is definitely X.",
            confidence=0.90,
            evidence_refs=[],
            escalation_reason=None,
        )
        issues = {v.issue for v in result.violations}
        assert RationaleIssue.UNSUPPORTED_CERTAINTY in issues

    def test_unsupported_certainty_high_confidence_one_ref(self) -> None:
        """Confidence > 0.85 and only 1 ref triggers the violation."""
        validator = _make_validator()
        result = validator.validate(
            incident_id="inc-v4",
            narrative="This is definitely the root cause.",
            confidence=0.86,
            evidence_refs=["ref-1"],
            escalation_reason=None,
        )
        issues = {v.issue for v in result.violations}
        assert RationaleIssue.UNSUPPORTED_CERTAINTY in issues

    def test_no_unsupported_certainty_when_two_refs(self) -> None:
        """Two references at high confidence should NOT trigger the violation."""
        validator = _make_validator()
        result = validator.validate(
            incident_id="inc-v5",
            narrative="This is the root cause.",
            confidence=0.90,
            evidence_refs=["ref-1", "ref-2"],
            escalation_reason=None,
        )
        issues = {v.issue for v in result.violations}
        assert RationaleIssue.UNSUPPORTED_CERTAINTY not in issues

    def test_no_unsupported_certainty_below_threshold(self) -> None:
        """Confidence <= 0.85 with no evidence should NOT trigger UNSUPPORTED_CERTAINTY."""
        validator = _make_validator()
        result = validator.validate(
            incident_id="inc-v6",
            narrative="This might be the root cause.",
            confidence=0.80,
            evidence_refs=[],
            escalation_reason=None,
        )
        issues = {v.issue for v in result.violations}
        assert RationaleIssue.UNSUPPORTED_CERTAINTY not in issues

    # ---- MISSING_EVIDENCE_LINK --------------------------------------------

    def test_missing_evidence_link_because_no_refs(self) -> None:
        validator = _make_validator()
        result = validator.validate(
            incident_id="inc-v7",
            narrative="The API failed because of a database timeout.",
            confidence=0.60,
            evidence_refs=[],
            escalation_reason=None,
        )
        issues = {v.issue for v in result.violations}
        assert RationaleIssue.MISSING_EVIDENCE_LINK in issues

    def test_missing_evidence_link_caused_by_no_refs(self) -> None:
        validator = _make_validator()
        result = validator.validate(
            incident_id="inc-v8",
            narrative="Downtime was caused by an upstream dependency failure.",
            confidence=0.60,
            evidence_refs=[],
            escalation_reason=None,
        )
        issues = {v.issue for v in result.violations}
        assert RationaleIssue.MISSING_EVIDENCE_LINK in issues

    def test_no_missing_evidence_link_with_refs(self) -> None:
        """Causal language with at least one ref should not trigger this violation."""
        validator = _make_validator()
        result = validator.validate(
            incident_id="inc-v9",
            narrative="The API failed because of a database timeout.",
            confidence=0.60,
            evidence_refs=["ref-1"],
            escalation_reason=None,
        )
        issues = {v.issue for v in result.violations}
        assert RationaleIssue.MISSING_EVIDENCE_LINK not in issues

    def test_no_missing_evidence_link_without_causal_language(self) -> None:
        validator = _make_validator()
        result = validator.validate(
            incident_id="inc-v10",
            narrative="The service had elevated error rates.",
            confidence=0.60,
            evidence_refs=[],
            escalation_reason=None,
        )
        issues = {v.issue for v in result.violations}
        assert RationaleIssue.MISSING_EVIDENCE_LINK not in issues

    # ---- UNEXPLAINED_ESCALATION ------------------------------------------

    def test_unexplained_escalation_narrative_mentions_escalation_no_reason(self) -> None:
        validator = _make_validator()
        result = validator.validate(
            incident_id="inc-v11",
            narrative="We recommend escalating this incident to senior on-call.",
            confidence=0.65,
            evidence_refs=["ref-1"],
            escalation_reason=None,
        )
        issues = {v.issue for v in result.violations}
        assert RationaleIssue.UNEXPLAINED_ESCALATION in issues

    def test_unexplained_escalation_empty_string_reason(self) -> None:
        validator = _make_validator()
        result = validator.validate(
            incident_id="inc-v12",
            narrative="Escalation is required immediately.",
            confidence=0.65,
            evidence_refs=[],
            escalation_reason="",
        )
        issues = {v.issue for v in result.violations}
        assert RationaleIssue.UNEXPLAINED_ESCALATION in issues

    def test_no_unexplained_escalation_when_reason_provided(self) -> None:
        validator = _make_validator()
        result = validator.validate(
            incident_id="inc-v13",
            narrative="We are escalating because the SLA breach is imminent.",
            confidence=0.65,
            evidence_refs=[],
            escalation_reason="SLA breach risk within 15 minutes.",
        )
        issues = {v.issue for v in result.violations}
        assert RationaleIssue.UNEXPLAINED_ESCALATION not in issues

    def test_no_unexplained_escalation_when_not_mentioned(self) -> None:
        """No escalation mention in narrative → no violation regardless of reason."""
        validator = _make_validator()
        result = validator.validate(
            incident_id="inc-v14",
            narrative="The service recovered after a restart.",
            confidence=0.70,
            evidence_refs=["ref-1"],
            escalation_reason=None,
        )
        issues = {v.issue for v in result.violations}
        assert RationaleIssue.UNEXPLAINED_ESCALATION not in issues

    # ---- CONTRADICTORY_NARRATIVE -----------------------------------------

    def test_contradictory_resolved_and_unresolved(self) -> None:
        validator = _make_validator()
        result = validator.validate(
            incident_id="inc-v15",
            narrative="The incident is resolved and the incident is unresolved.",
            confidence=0.60,
            evidence_refs=[],
            escalation_reason=None,
        )
        issues = {v.issue for v in result.violations}
        assert RationaleIssue.CONTRADICTORY_NARRATIVE in issues

    def test_contradictory_stable_and_degrading(self) -> None:
        validator = _make_validator()
        result = validator.validate(
            incident_id="inc-v16",
            narrative="The system appears stable but is clearly degrading.",
            confidence=0.60,
            evidence_refs=[],
            escalation_reason=None,
        )
        issues = {v.issue for v in result.violations}
        assert RationaleIssue.CONTRADICTORY_NARRATIVE in issues

    def test_no_contradiction_single_state(self) -> None:
        validator = _make_validator()
        result = validator.validate(
            incident_id="inc-v17",
            narrative="The system is stable.",
            confidence=0.70,
            evidence_refs=["ref-1", "ref-2"],
            escalation_reason=None,
        )
        issues = {v.issue for v in result.violations}
        assert RationaleIssue.CONTRADICTORY_NARRATIVE not in issues

    # ---- OVER_SPECIFIC_CLAIM ---------------------------------------------

    def test_over_specific_claim_low_confidence_with_percentage(self) -> None:
        validator = _make_validator()
        result = validator.validate(
            incident_id="inc-v18",
            narrative="Error rate increased by exactly 73.42% during the window.",
            confidence=0.30,
            evidence_refs=[],
            escalation_reason=None,
        )
        issues = {v.issue for v in result.violations}
        assert RationaleIssue.OVER_SPECIFIC_CLAIM in issues

    def test_no_over_specific_claim_above_threshold(self) -> None:
        """Confidence >= 0.40 should not trigger OVER_SPECIFIC_CLAIM."""
        validator = _make_validator()
        result = validator.validate(
            incident_id="inc-v19",
            narrative="Error rate increased by 73.42%.",
            confidence=0.45,
            evidence_refs=[],
            escalation_reason=None,
        )
        issues = {v.issue for v in result.violations}
        assert RationaleIssue.OVER_SPECIFIC_CLAIM not in issues

    def test_no_over_specific_claim_without_percentage(self) -> None:
        validator = _make_validator()
        result = validator.validate(
            incident_id="inc-v20",
            narrative="Error rate increased significantly.",
            confidence=0.25,
            evidence_refs=[],
            escalation_reason=None,
        )
        issues = {v.issue for v in result.violations}
        assert RationaleIssue.OVER_SPECIFIC_CLAIM not in issues

    # ---- Severity and passed logic ---------------------------------------

    def test_passed_false_on_high_severity_violation(self) -> None:
        validator = _make_validator()
        result = validator.validate(
            incident_id="inc-v21",
            narrative="Root cause is definitely X because of Y.",
            confidence=0.91,
            evidence_refs=[],
            escalation_reason=None,
        )
        # UNSUPPORTED_CERTAINTY (high) and MISSING_EVIDENCE_LINK (high) expected
        assert result.passed is False
        assert result.high_severity_count >= 1

    def test_passed_true_only_medium_violations(self) -> None:
        """Medium-only violations still yield passed=True."""
        validator = _make_validator()
        # OVER_SPECIFIC_CLAIM is medium severity
        result = validator.validate(
            incident_id="inc-v22",
            narrative="Error rate spiked to 12.34%.",
            confidence=0.35,
            evidence_refs=["ref-1", "ref-2"],
            escalation_reason=None,
        )
        if result.violations:
            severities = {v.severity for v in result.violations}
            if "high" not in severities:
                assert result.passed is True

    def test_total_violations_matches_list_length(self) -> None:
        validator = _make_validator()
        result = validator.validate(
            incident_id="inc-v23",
            narrative="Service stable and degrading. Root cause because of X.",
            confidence=0.92,
            evidence_refs=[],
            escalation_reason=None,
        )
        assert result.total_violations == len(result.violations)


# ===========================================================================
# NarrativeConsistencyChecker
# ===========================================================================


class TestNarrativeConsistencyChecker:
    # ---- Empty / single input --------------------------------------------

    def test_empty_narratives_returns_consistent(self) -> None:
        checker = _make_checker()
        report = checker.check(
            incident_id="inc-n0",
            narratives=[],
            confidences=[],
            timestamps_iso=[],
        )
        assert isinstance(report, NarrativeConsistencyReport)
        assert report.is_consistent is True
        assert report.temporal_coherence_score == 1.0
        assert report.confidence_drift_detected is False

    def test_single_narrative_no_violations(self) -> None:
        checker = _make_checker()
        report = checker.check(
            incident_id="inc-n1",
            narratives=["Service is healthy."],
            confidences=[0.80],
            timestamps_iso=["2026-05-15T10:00:00Z"],
        )
        assert report.is_consistent is True
        assert report.violations == []

    # ---- Temporal coherence ----------------------------------------------

    def test_ordered_timestamps_score_1(self) -> None:
        checker = _make_checker()
        report = checker.check(
            incident_id="inc-n2",
            narratives=["A", "B", "C"],
            confidences=[0.80, 0.78, 0.76],
            timestamps_iso=[
                "2026-05-15T10:00:00Z",
                "2026-05-15T10:05:00Z",
                "2026-05-15T10:10:00Z",
            ],
        )
        assert report.temporal_coherence_score == pytest.approx(1.0)
        types = [v.violation_type for v in report.violations]
        assert "TEMPORAL_ORDER" not in types

    def test_one_out_of_order_pair_deducts_0_2(self) -> None:
        checker = _make_checker()
        report = checker.check(
            incident_id="inc-n3",
            narratives=["A", "B"],
            confidences=[0.80, 0.78],
            timestamps_iso=[
                "2026-05-15T10:05:00Z",
                "2026-05-15T10:00:00Z",  # reversed!
            ],
        )
        assert report.temporal_coherence_score == pytest.approx(0.8)
        assert any(v.violation_type == "TEMPORAL_ORDER" for v in report.violations)

    def test_two_out_of_order_pairs_deduct_0_4(self) -> None:
        checker = _make_checker()
        report = checker.check(
            incident_id="inc-n4",
            narratives=["A", "B", "C"],
            confidences=[0.80, 0.78, 0.76],
            timestamps_iso=[
                "2026-05-15T10:10:00Z",
                "2026-05-15T10:05:00Z",  # reversed
                "2026-05-15T10:00:00Z",  # reversed
            ],
        )
        assert report.temporal_coherence_score == pytest.approx(0.6)

    def test_temporal_coherence_clamped_to_zero(self) -> None:
        checker = _make_checker()
        report = checker.check(
            incident_id="inc-n5",
            narratives=["A", "B", "C", "D", "E", "F"],
            confidences=[0.80] * 6,
            timestamps_iso=[
                "2026-05-15T10:10:00Z",
                "2026-05-15T10:05:00Z",
                "2026-05-15T10:00:00Z",
                "2026-05-15T09:55:00Z",
                "2026-05-15T09:50:00Z",
                "2026-05-15T09:45:00Z",
            ],
        )
        assert report.temporal_coherence_score >= 0.0

    def test_temporal_violation_makes_report_inconsistent(self) -> None:
        checker = _make_checker()
        report = checker.check(
            incident_id="inc-n6",
            narratives=["A", "B"],
            confidences=[0.80, 0.80],
            timestamps_iso=[
                "2026-05-15T10:05:00Z",
                "2026-05-15T10:00:00Z",
            ],
        )
        # TEMPORAL_ORDER violations are "high" → is_consistent = False
        assert report.is_consistent is False

    # ---- Confidence drift ------------------------------------------------

    def test_confidence_drift_detected_above_threshold(self) -> None:
        checker = _make_checker()
        report = checker.check(
            incident_id="inc-n7",
            narratives=["A", "B"],
            confidences=[0.90, 0.45],  # drift = 0.45 > 0.40
            timestamps_iso=[
                "2026-05-15T10:00:00Z",
                "2026-05-15T10:05:00Z",
            ],
        )
        assert report.confidence_drift_detected is True
        assert any(v.violation_type == "CONFIDENCE_DRIFT" for v in report.violations)

    def test_confidence_drift_not_detected_below_threshold(self) -> None:
        checker = _make_checker()
        report = checker.check(
            incident_id="inc-n8",
            narratives=["A", "B"],
            confidences=[0.80, 0.45],  # drift = 0.35 <= 0.40
            timestamps_iso=[
                "2026-05-15T10:00:00Z",
                "2026-05-15T10:05:00Z",
            ],
        )
        assert report.confidence_drift_detected is False

    def test_confidence_drift_exactly_at_threshold_not_flagged(self) -> None:
        """Drift must be strictly greater than 0.40 to trigger."""
        checker = _make_checker()
        report = checker.check(
            incident_id="inc-n9",
            narratives=["A", "B"],
            confidences=[0.80, 0.40],  # drift = 0.40, not > 0.40
            timestamps_iso=[
                "2026-05-15T10:00:00Z",
                "2026-05-15T10:05:00Z",
            ],
        )
        assert report.confidence_drift_detected is False

    def test_confidence_drift_violation_is_medium_severity(self) -> None:
        checker = _make_checker()
        report = checker.check(
            incident_id="inc-n10",
            narratives=["A", "B"],
            confidences=[0.95, 0.50],
            timestamps_iso=[
                "2026-05-15T10:00:00Z",
                "2026-05-15T10:05:00Z",
            ],
        )
        drift_violations = [v for v in report.violations if v.violation_type == "CONFIDENCE_DRIFT"]
        assert len(drift_violations) == 1
        assert drift_violations[0].severity == "medium"

    def test_confidence_drift_alone_does_not_make_inconsistent(self) -> None:
        """Drift is medium severity; alone it should not set is_consistent=False."""
        checker = _make_checker()
        report = checker.check(
            incident_id="inc-n11",
            narratives=["A", "B"],
            confidences=[0.95, 0.50],
            timestamps_iso=[
                "2026-05-15T10:00:00Z",
                "2026-05-15T10:05:00Z",
            ],
        )
        high_violations = [v for v in report.violations if v.severity == "high"]
        if not high_violations:
            assert report.is_consistent is True

    # ---- Contradiction detection -----------------------------------------

    def test_resolved_then_unresolved_is_contradiction(self) -> None:
        checker = _make_checker()
        report = checker.check(
            incident_id="inc-n12",
            narratives=[
                "The incident has been resolved.",
                "The issue remains unresolved and is escalating.",
            ],
            confidences=[0.80, 0.75],
            timestamps_iso=[
                "2026-05-15T10:00:00Z",
                "2026-05-15T10:05:00Z",
            ],
        )
        assert any(v.violation_type == "CONTRADICTION" for v in report.violations)

    def test_stable_then_degrading_is_contradiction(self) -> None:
        checker = _make_checker()
        report = checker.check(
            incident_id="inc-n13",
            narratives=[
                "System is stable and responding normally.",
                "System is now degrading under load.",
            ],
            confidences=[0.80, 0.70],
            timestamps_iso=[
                "2026-05-15T10:00:00Z",
                "2026-05-15T10:05:00Z",
            ],
        )
        assert any(v.violation_type == "CONTRADICTION" for v in report.violations)

    def test_healthy_then_unhealthy_is_contradiction(self) -> None:
        checker = _make_checker()
        report = checker.check(
            incident_id="inc-n14",
            narratives=[
                "All services are healthy.",
                "The payment service is unhealthy.",
            ],
            confidences=[0.80, 0.72],
            timestamps_iso=[
                "2026-05-15T10:00:00Z",
                "2026-05-15T10:05:00Z",
            ],
        )
        assert any(v.violation_type == "CONTRADICTION" for v in report.violations)

    def test_improving_then_worsening_is_contradiction(self) -> None:
        checker = _make_checker()
        report = checker.check(
            incident_id="inc-n15",
            narratives=[
                "Error rates are improving.",
                "Error rates are worsening again.",
            ],
            confidences=[0.75, 0.70],
            timestamps_iso=[
                "2026-05-15T10:00:00Z",
                "2026-05-15T10:10:00Z",
            ],
        )
        assert any(v.violation_type == "CONTRADICTION" for v in report.violations)

    def test_no_contradiction_consistent_narratives(self) -> None:
        checker = _make_checker()
        report = checker.check(
            incident_id="inc-n16",
            narratives=[
                "Service is experiencing elevated error rates.",
                "Error rates have increased further. Team is investigating.",
                "Root cause identified as database connection pool exhaustion.",
            ],
            confidences=[0.60, 0.65, 0.80],
            timestamps_iso=[
                "2026-05-15T10:00:00Z",
                "2026-05-15T10:05:00Z",
                "2026-05-15T10:10:00Z",
            ],
        )
        contradiction_violations = [
            v for v in report.violations if v.violation_type == "CONTRADICTION"
        ]
        assert contradiction_violations == []

    def test_contradiction_violation_is_high_severity(self) -> None:
        checker = _make_checker()
        report = checker.check(
            incident_id="inc-n17",
            narratives=[
                "The system is stable.",
                "The system is degrading.",
            ],
            confidences=[0.80, 0.75],
            timestamps_iso=[
                "2026-05-15T10:00:00Z",
                "2026-05-15T10:05:00Z",
            ],
        )
        contradiction_violations = [
            v for v in report.violations if v.violation_type == "CONTRADICTION"
        ]
        assert len(contradiction_violations) >= 1
        assert all(v.severity == "high" for v in contradiction_violations)

    def test_contradiction_makes_report_inconsistent(self) -> None:
        checker = _make_checker()
        report = checker.check(
            incident_id="inc-n18",
            narratives=[
                "Service is healthy.",
                "Service is unhealthy.",
            ],
            confidences=[0.80, 0.75],
            timestamps_iso=[
                "2026-05-15T10:00:00Z",
                "2026-05-15T10:05:00Z",
            ],
        )
        assert report.is_consistent is False

    def test_reverse_antonym_order_also_detected(self) -> None:
        """Earlier: 'unresolved', later: 'resolved' should also be a contradiction."""
        checker = _make_checker()
        report = checker.check(
            incident_id="inc-n19",
            narratives=[
                "The issue is unresolved.",
                "The issue is resolved.",
            ],
            confidences=[0.70, 0.80],
            timestamps_iso=[
                "2026-05-15T10:00:00Z",
                "2026-05-15T10:05:00Z",
            ],
        )
        assert any(v.violation_type == "CONTRADICTION" for v in report.violations)

    # ---- Report structure ------------------------------------------------

    def test_report_fields_populated(self) -> None:
        checker = _make_checker()
        report = checker.check(
            incident_id="inc-n20",
            narratives=["Service healthy.", "Service degrading."],
            confidences=[0.80, 0.60],
            timestamps_iso=[
                "2026-05-15T10:00:00Z",
                "2026-05-15T10:05:00Z",
            ],
        )
        assert report.incident_id == "inc-n20"
        assert isinstance(report.violations, list)
        assert isinstance(report.temporal_coherence_score, float)
        assert isinstance(report.is_consistent, bool)
        assert isinstance(report.confidence_drift_detected, bool)
