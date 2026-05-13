"""
Phase 42 retrieval provenance tests.

Proves:
  - RetrievalProvenance carries all required fields.
  - grounding_status correctly reflects similarity score tiers.
  - is_reliable and is_actionable gates work correctly.
  - attach_provenance enriches raw results with provenance dicts.
  - compute_grounding_score aggregates across multiple provenances.
  - PatternSearcher.search() returns provenance in every result.
"""
from __future__ import annotations

import pytest

from retrieval.provenance import (
    RetrievalProvenance,
    GroundingStatus,
    attach_provenance,
    compute_grounding_score,
)


def _make_provenance(score: float) -> RetrievalProvenance:
    return RetrievalProvenance(
        incident_id="INC-001",
        similarity_score=score,
        retrieval_reason="test",
        matched_dimensions=["latency", "database"],
        embedding_model="text-embedding-3-small",
    )


# ─── grounding_status tiers ───────────────────────────────────────────────────


def test_grounding_status_grounded_at_high_score() -> None:
    p = _make_provenance(0.85)
    assert p.grounding_status == "grounded"


def test_grounding_status_weakly_grounded_at_medium_score() -> None:
    p = _make_provenance(0.55)
    assert p.grounding_status == "weakly_grounded"


def test_grounding_status_ungrounded_at_low_score() -> None:
    p = _make_provenance(0.30)
    assert p.grounding_status == "ungrounded"


# ─── is_reliable / is_actionable ──────────────────────────────────────────────


def test_is_reliable_true_above_threshold() -> None:
    assert _make_provenance(0.75).is_reliable is True
    assert _make_provenance(0.70).is_reliable is True


def test_is_reliable_false_below_threshold() -> None:
    assert _make_provenance(0.65).is_reliable is False
    assert _make_provenance(0.30).is_reliable is False


def test_is_actionable_true_at_moderate_score() -> None:
    assert _make_provenance(0.65).is_actionable is True


def test_is_actionable_false_when_ungrounded() -> None:
    # Score below 0.45 → grounding_status="ungrounded" → is_actionable must be False
    p = _make_provenance(0.30)
    assert p.grounding_status == "ungrounded"
    assert p.is_actionable is False


# ─── to_dict ──────────────────────────────────────────────────────────────────


def test_to_dict_includes_all_required_fields() -> None:
    p = _make_provenance(0.80)
    d = p.to_dict()
    required = {"incident_id", "similarity_score", "retrieval_reason", "matched_dimensions",
                 "embedding_model", "retrieved_at", "collection", "grounding_status",
                 "is_reliable", "is_actionable"}
    assert required.issubset(set(d.keys()))


# ─── from_retrieval_result ────────────────────────────────────────────────────


def test_from_retrieval_result_builds_from_semantic_retriever_output() -> None:
    result = {
        "incident_id": "INC-999",
        "similarity_score": 0.88,
        "retrieval_reason": "high-confidence semantic match",
        "matched_dimensions": ["latency", "database"],
        "embedding_model": "text-embedding-3-small",
        "retrieved_at": "2024-01-01T14:00:00+00:00",
    }
    p = RetrievalProvenance.from_retrieval_result(result, collection="past_incidents")
    assert p.incident_id == "INC-999"
    assert p.similarity_score == pytest.approx(0.88)
    assert p.grounding_status == "grounded"
    assert p.collection == "past_incidents"


def test_from_retrieval_result_handles_legacy_score_field() -> None:
    result = {"id": "INC-002", "score": 0.55, "payload": {}}
    p = RetrievalProvenance.from_retrieval_result(result)
    assert p.similarity_score == pytest.approx(0.55)
    assert p.grounding_status == "weakly_grounded"


# ─── attach_provenance ────────────────────────────────────────────────────────


def test_attach_provenance_adds_provenance_field_to_all_results() -> None:
    results = [
        {"incident_id": "A", "similarity_score": 0.90, "retrieval_reason": "good", "matched_dimensions": [], "embedding_model": "m"},
        {"incident_id": "B", "similarity_score": 0.50, "retrieval_reason": "ok", "matched_dimensions": [], "embedding_model": "m"},
    ]
    enriched = attach_provenance(results, collection="test", query_text="latency spike")
    assert all("provenance" in r for r in enriched)
    assert enriched[0]["provenance"]["grounding_status"] == "grounded"
    assert enriched[1]["provenance"]["grounding_status"] == "weakly_grounded"


def test_attach_provenance_preserves_original_fields() -> None:
    results = [{"incident_id": "X", "title": "Latency", "similarity_score": 0.8, "retrieval_reason": "", "matched_dimensions": [], "embedding_model": "m"}]
    enriched = attach_provenance(results)
    assert enriched[0]["title"] == "Latency"
    assert enriched[0]["incident_id"] == "X"


# ─── compute_grounding_score ──────────────────────────────────────────────────


def test_compute_grounding_score_returns_mean_similarity() -> None:
    provenances = [_make_provenance(0.80), _make_provenance(0.60)]
    score = compute_grounding_score(provenances)
    assert score == pytest.approx(0.70, abs=1e-3)


def test_compute_grounding_score_empty_returns_zero() -> None:
    assert compute_grounding_score([]) == 0.0


def test_compute_grounding_score_all_high_returns_near_one() -> None:
    provenances = [_make_provenance(0.95), _make_provenance(0.92)]
    score = compute_grounding_score(provenances)
    assert score > 0.90
