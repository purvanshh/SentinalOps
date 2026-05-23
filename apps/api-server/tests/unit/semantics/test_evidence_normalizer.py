"""
Phase 45 evidence normalizer tests.

Proves:
  - normalize_text() maps DB timeout text to db_connection_exhaustion concept.
  - normalize_text() maps consumer lag text to queue_consumer_lag concept.
  - normalize_text() maps retry text to retry_amplification concept.
  - normalize_text() returns is_normalized=False for unrecognized text.
  - normalize_text() confidence scales with matched keyword count.
  - normalize_evidence_items() adds semantic fields to each recognized item.
  - normalize_evidence_items() leaves unrecognized items without semantic fields.
  - cluster_by_concept() groups items sharing the same canonical concept.
  - cluster_by_concept() puts unrecognized items in 'unclassified'.
  - dominant_mechanism_hints() returns most frequent mechanism ID first.
"""

from __future__ import annotations

import pytest
from semantics.evidence_normalizer import SemanticEvidenceNormalizer


@pytest.fixture()
def normalizer() -> SemanticEvidenceNormalizer:
    return SemanticEvidenceNormalizer()


def test_normalize_db_timeout(normalizer: SemanticEvidenceNormalizer) -> None:
    result = normalizer.normalize_text("DB timeout spike and connection pool wait")
    assert result.is_normalized
    assert result.canonical_concept is not None
    assert result.canonical_concept.canonical_id == "db_connection_exhaustion"


def test_normalize_consumer_lag(normalizer: SemanticEvidenceNormalizer) -> None:
    result = normalizer.normalize_text("consumer lag kafka lag growing queue depth backlog")
    assert result.is_normalized
    assert result.canonical_concept is not None
    assert result.canonical_concept.canonical_id == "queue_consumer_lag"


def test_normalize_retry_storm(normalizer: SemanticEvidenceNormalizer) -> None:
    result = normalizer.normalize_text("retry storm and exponential backoff cascading retries")
    assert result.is_normalized
    assert result.canonical_concept is not None
    assert result.canonical_concept.canonical_id == "retry_amplification"


def test_normalize_lock_contention(normalizer: SemanticEvidenceNormalizer) -> None:
    result = normalizer.normalize_text("deadlock detected lock wait row lock contention")
    assert result.is_normalized
    assert result.canonical_concept is not None
    assert result.canonical_concept.canonical_id == "db_lock_contention"


def test_normalize_thread_pool_saturation(normalizer: SemanticEvidenceNormalizer) -> None:
    result = normalizer.normalize_text("thread pool exhaustion thread starvation blocked threads")
    assert result.is_normalized
    assert result.canonical_concept is not None
    assert result.canonical_concept.canonical_id == "thread_pool_saturation"


def test_normalize_memory_exhaustion(normalizer: SemanticEvidenceNormalizer) -> None:
    result = normalizer.normalize_text("gc pause heap exhaustion out of memory memory pressure")
    assert result.is_normalized
    assert result.canonical_concept is not None
    assert result.canonical_concept.canonical_id == "memory_exhaustion"


def test_normalize_cascading_failure(normalizer: SemanticEvidenceNormalizer) -> None:
    result = normalizer.normalize_text("cascading failure spreading across services blast radius")
    assert result.is_normalized
    assert result.canonical_concept is not None
    assert result.canonical_concept.canonical_id == "cascading_service_failure"


def test_normalize_unrecognized_text(normalizer: SemanticEvidenceNormalizer) -> None:
    result = normalizer.normalize_text("everything nominal, all green, cpu stable, no issues")
    assert not result.is_normalized
    assert result.canonical_concept is None
    assert result.confidence == 0.0


def test_normalize_confidence_scales_with_matches(normalizer: SemanticEvidenceNormalizer) -> None:
    one_match = normalizer.normalize_text("connection pool")
    many_matches = normalizer.normalize_text(
        "connection pool exhausted db timeout pool starvation connection wait"
    )
    assert many_matches.confidence >= one_match.confidence


def test_normalize_confidence_capped_at_one(normalizer: SemanticEvidenceNormalizer) -> None:
    text = " ".join(
        [
            "connection pool",
            "pool exhausted",
            "db timeout",
            "connection wait",
            "acquisition latency",
            "connection limit",
            "waiting for connection",
            "pool starvation",
            "db connections",
        ]
    )
    result = normalizer.normalize_text(text)
    assert result.confidence <= 1.0


def test_normalize_evidence_items_adds_fields(normalizer: SemanticEvidenceNormalizer) -> None:
    items = [
        {"summary": "connection pool exhausted db timeout", "item_key": "e1"},
        {"summary": "consumer lag kafka lag growing", "item_key": "e2"},
    ]
    enriched = normalizer.normalize_evidence_items(items)
    assert len(enriched) == 2

    first = enriched[0]
    assert "semantic_concept_id" in first
    assert first["semantic_concept_id"] == "db_connection_exhaustion"
    assert "operational_meaning" in first
    assert "mechanism_hints" in first
    assert isinstance(first["mechanism_hints"], list)


def test_normalize_evidence_items_skips_unrecognized(  # noqa: E501
    normalizer: SemanticEvidenceNormalizer,
) -> None:
    items = [
        {"summary": "all systems green no issues", "item_key": "e1"},
    ]
    enriched = normalizer.normalize_evidence_items(items)
    assert "semantic_concept_id" not in enriched[0]


def test_normalize_evidence_items_preserves_original_keys(  # noqa: E501
    normalizer: SemanticEvidenceNormalizer,
) -> None:
    items = [{"summary": "connection pool exhausted", "item_key": "e1", "severity": "HIGH"}]
    enriched = normalizer.normalize_evidence_items(items)
    assert enriched[0]["item_key"] == "e1"
    assert enriched[0]["severity"] == "HIGH"


def test_cluster_by_concept(normalizer: SemanticEvidenceNormalizer) -> None:
    items = [
        {"summary": "connection pool exhausted db timeout", "item_key": "e1"},
        {"summary": "pool starvation connection wait", "item_key": "e2"},
        {"summary": "consumer lag kafka lag", "item_key": "e3"},
        {"summary": "completely unrelated stuff", "item_key": "e4"},
    ]
    clusters = normalizer.cluster_by_concept(items)

    assert "db_connection_exhaustion" in clusters
    assert len(clusters["db_connection_exhaustion"]) == 2

    assert "queue_consumer_lag" in clusters
    assert len(clusters["queue_consumer_lag"]) == 1

    assert "unclassified" in clusters
    assert len(clusters["unclassified"]) == 1


def test_dominant_mechanism_hints(normalizer: SemanticEvidenceNormalizer) -> None:
    items = [
        {"summary": "connection pool exhausted db timeout pool starvation", "item_key": "e1"},
        {"summary": "connection wait pool exhausted db connections", "item_key": "e2"},
        {"summary": "consumer lag kafka lag", "item_key": "e3"},
    ]
    hints = normalizer.dominant_mechanism_hints(items)
    assert isinstance(hints, list)
    # connection pool evidence dominates → connection_pool_starvation hint should come first
    assert "connection_pool_starvation" in hints
    assert (
        hints.index("connection_pool_starvation") < hints.index("queue_buildup_backpressure")
        if "queue_buildup_backpressure" in hints
        else True
    )


def test_dominant_mechanism_hints_empty(normalizer: SemanticEvidenceNormalizer) -> None:
    hints = normalizer.dominant_mechanism_hints([])
    assert hints == []
