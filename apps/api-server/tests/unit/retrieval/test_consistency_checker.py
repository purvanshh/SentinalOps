"""
Phase 42 retrieval hallucination suppression tests.

Proves:
  - suppress_low_grounding_results filters below-threshold results.
  - check_claim_support returns True only when similarity + keyword overlap both pass.
  - run_consistency_check produces a ConsistencyReport with correct fields.
  - ConsistencyReport.is_trustworthy reflects grounding quality and unsupported claims.
  - UnsupportedClaim carries claim text, reason, and max_similarity.
"""
from __future__ import annotations

import pytest

from retrieval.consistency_checker import (
    ConsistencyReport,
    UnsupportedClaim,
    check_claim_support,
    run_consistency_check,
    suppress_low_grounding_results,
)


def _make_result(
    score: float,
    title: str = "",
    description: str = "",
    incident_id: str = "INC-TEST",
) -> dict:
    return {
        "incident_id": incident_id,
        "title": title,
        "description": description,
        "provenance": {"similarity_score": score},
        "match_score": score,
    }


# ─── suppress_low_grounding_results ──────────────────────────────────────────


def test_suppress_keeps_results_above_threshold() -> None:
    results = [_make_result(0.70), _make_result(0.80)]
    kept, suppressed = suppress_low_grounding_results(results, min_score=0.45)
    assert len(kept) == 2
    assert suppressed == []


def test_suppress_removes_results_below_threshold() -> None:
    results = [_make_result(0.30, incident_id="LOW"), _make_result(0.80, incident_id="HIGH")]
    kept, suppressed = suppress_low_grounding_results(results, min_score=0.45)
    assert len(kept) == 1
    assert "LOW" in suppressed


def test_suppress_all_low_returns_empty_kept() -> None:
    results = [_make_result(0.20), _make_result(0.10)]
    kept, suppressed = suppress_low_grounding_results(results, min_score=0.45)
    assert kept == []
    assert len(suppressed) == 2


def test_suppress_empty_input_returns_empty() -> None:
    kept, suppressed = suppress_low_grounding_results([])
    assert kept == []
    assert suppressed == []


# ─── check_claim_support ─────────────────────────────────────────────────────


def test_claim_support_true_when_score_and_keyword_match() -> None:
    results = [_make_result(0.80, title="database connection timeout")]
    assert check_claim_support("database timeout caused the incident", results) is True


def test_claim_support_false_when_score_too_low() -> None:
    results = [_make_result(0.30, title="database connection timeout")]
    assert check_claim_support("database timeout", results) is False


def test_claim_support_false_when_no_keyword_overlap() -> None:
    results = [_make_result(0.90, title="unrelated metric anomaly")]
    # claim has no keywords overlapping with "unrelated metric anomaly"
    assert check_claim_support("payment gateway certificate expired", results) is False


def test_claim_support_uses_description_field() -> None:
    results = [_make_result(0.75, description="postgres connection pool exhausted")]
    assert check_claim_support("postgres pool exhausted", results) is True


def test_claim_support_empty_results_returns_false() -> None:
    assert check_claim_support("database timeout", []) is False


def test_claim_support_empty_claim_returns_false() -> None:
    results = [_make_result(0.90, title="database timeout")]
    assert check_claim_support("", results) is False


# ─── run_consistency_check ────────────────────────────────────────────────────


def test_consistency_check_supported_claim_listed() -> None:
    results = [_make_result(0.85, title="database latency spike detected")]
    report = run_consistency_check(["database latency spike"], results)
    assert "database latency spike" in report.supported_claims
    assert report.unsupported_claims == []


def test_consistency_check_unsupported_claim_listed() -> None:
    results = [_make_result(0.85, title="unrelated cpu burst")]
    report = run_consistency_check(["payment certificate expired"], results)
    assert len(report.unsupported_claims) == 1
    assert isinstance(report.unsupported_claims[0], UnsupportedClaim)


def test_consistency_check_suppression_removes_low_score_result() -> None:
    results = [
        _make_result(0.20, incident_id="LOW"),
        _make_result(0.85, title="database timeout", incident_id="HIGH"),
    ]
    report = run_consistency_check(["database timeout"], results)
    assert "LOW" in report.suppressed_results


def test_consistency_check_grounding_score_reflects_kept_results() -> None:
    results = [_make_result(0.80), _make_result(0.70)]
    report = run_consistency_check([], results)
    assert report.grounding_score == pytest.approx(0.75, abs=0.01)


def test_consistency_check_is_trustworthy_when_all_claims_supported() -> None:
    results = [_make_result(0.80, title="database connection pool exhausted")]
    report = run_consistency_check(["database connection pool"], results)
    assert report.is_trustworthy is True


def test_consistency_check_not_trustworthy_with_unsupported_claims() -> None:
    results = [_make_result(0.80, title="cpu spike")]
    report = run_consistency_check(["payment certificate expired"], results)
    assert report.is_trustworthy is False


def test_consistency_check_not_trustworthy_below_grounding_threshold() -> None:
    results = [_make_result(0.10), _make_result(0.15)]
    report = run_consistency_check([], results)
    assert report.grounding_score < 0.45
    assert report.is_trustworthy is False


def test_consistency_check_suppression_count_matches_suppressed_list() -> None:
    results = [_make_result(0.10, incident_id="A"), _make_result(0.15, incident_id="B")]
    report = run_consistency_check([], results)
    assert report.suppression_count == len(report.suppressed_results)


def test_unsupported_claim_carries_max_similarity() -> None:
    results = [_make_result(0.72, title="cache eviction storm")]
    report = run_consistency_check(["payment certificate expired"], results)
    assert len(report.unsupported_claims) == 1
    uc = report.unsupported_claims[0]
    assert uc.max_similarity == pytest.approx(0.72, abs=0.01)
    assert uc.retrieved_count == 1
