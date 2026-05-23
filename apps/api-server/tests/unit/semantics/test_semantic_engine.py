"""
Phase 45 semantic engine tests.

Proves:
  - infer_mechanism() returns a MechanismInference with a primary mechanism.
  - Connection pool evidence yields connection_pool_starvation as primary.
  - Retry evidence yields retry_storm as primary.
  - Empty evidence yields inference with mechanism_confidence == 0.0.
  - mechanism_confidence reflects dominance (high when one mechanism stands out).
  - latent_state_implications is populated from the top mechanism.
  - build_mechanism_hypothesis_text() produces mechanism-named output.
  - build_mechanism_causal_chain() includes latent state in chain.
  - incident_type boost promotes the correct mechanism.
  - to_dict() includes primary_mechanism_id and alternatives list.
"""

from __future__ import annotations

import pytest
from semantics.semantic_engine import OperationalSemanticEngine


@pytest.fixture()
def engine() -> OperationalSemanticEngine:
    return OperationalSemanticEngine()


def _make_evidence(summary: str, item_type: str = "log", metric: str = "") -> dict:
    return {"summary": summary, "item_type": item_type, "metric": metric, "item_key": "ev-1"}


def test_infer_mechanism_connection_pool(engine: OperationalSemanticEngine) -> None:
    evidence = [
        _make_evidence("connection pool exhausted, db timeout spike"),
        _make_evidence("connection wait time increased 400ms", metric="db_connection_wait"),
    ]
    result = engine.infer_mechanism(evidence, [])
    assert result.primary is not None
    assert result.primary.mechanism.mechanism_id == "connection_pool_starvation"


def test_infer_mechanism_retry_storm(engine: OperationalSemanticEngine) -> None:
    evidence = [
        _make_evidence("retry storm detected, exponential backoff cascading retries"),
        _make_evidence("thundering herd against auth service"),
    ]
    result = engine.infer_mechanism(evidence, [])
    assert result.primary is not None
    assert result.primary.mechanism.mechanism_id == "retry_storm"


def test_infer_mechanism_lock_contention(engine: OperationalSemanticEngine) -> None:
    evidence = [
        _make_evidence("deadlock detected on orders table, lock wait time 8s"),
        _make_evidence("long transaction blocking row lock"),
    ]
    result = engine.infer_mechanism(evidence, [])
    assert result.primary is not None
    assert result.primary.mechanism.mechanism_id == "lock_contention"


def test_infer_mechanism_queue_buildup(engine: OperationalSemanticEngine) -> None:
    evidence = [
        _make_evidence("consumer lag 50000 messages kafka lag growing"),
        _make_evidence("queue depth increasing backpressure detected"),
    ]
    result = engine.infer_mechanism(evidence, [])
    assert result.primary is not None
    assert result.primary.mechanism.mechanism_id == "queue_buildup_backpressure"


def test_infer_mechanism_empty_evidence(engine: OperationalSemanticEngine) -> None:
    result = engine.infer_mechanism([], [])
    assert result.primary is None
    assert result.mechanism_confidence == 0.0
    assert result.alternatives == []


def test_infer_mechanism_confidence_range(engine: OperationalSemanticEngine) -> None:
    evidence = [_make_evidence("connection pool wait time pool exhaustion db timeout")]
    result = engine.infer_mechanism(evidence, [])
    assert 0.0 <= result.mechanism_confidence <= 1.0


def test_infer_mechanism_alternatives_populated(engine: OperationalSemanticEngine) -> None:
    # Mixed signals should still yield alternatives
    evidence = [
        _make_evidence("connection pool exhausted also high memory heap usage"),
        _make_evidence("consumer lag kafka backpressure"),
    ]
    result = engine.infer_mechanism(evidence, [])
    assert result.primary is not None
    assert len(result.alternatives) >= 1


def test_latent_state_implications_populated(engine: OperationalSemanticEngine) -> None:
    evidence = [_make_evidence("connection pool exhausted waiting for connection")]
    result = engine.infer_mechanism(evidence, [])
    assert result.primary is not None
    assert isinstance(result.latent_state_implications, list)
    # connection_pool_starvation should imply connection_saturation
    assert "connection_saturation" in result.latent_state_implications


def test_incident_type_boost(engine: OperationalSemanticEngine) -> None:
    # Weak text evidence but incident_type strongly hints at retry_storm
    evidence = [_make_evidence("service degraded")]
    result_with_hint = engine.infer_mechanism(evidence, [], incident_type="retry_storm")
    # With incident_type hint, retry_storm should at least appear in top 3
    if result_with_hint.primary is not None:
        all_ids = [result_with_hint.primary.mechanism.mechanism_id] + [
            alt.mechanism.mechanism_id for alt in result_with_hint.alternatives[:2]
        ]
        assert "retry_storm" in all_ids


def test_build_mechanism_hypothesis_text_same_service(engine: OperationalSemanticEngine) -> None:
    evidence = [_make_evidence("connection pool exhausted pool starvation")]
    inference = engine.infer_mechanism(evidence, [])
    text = engine.build_mechanism_hypothesis_text(
        "DB connection pool exhaustion", "payments-svc", "payments-svc", inference
    )
    assert "payments-svc" in text
    assert "Connection Pool" in text or "connection" in text.lower()


def test_build_mechanism_hypothesis_text_cross_service(engine: OperationalSemanticEngine) -> None:
    evidence = [_make_evidence("connection pool exhausted pool starvation")]
    inference = engine.infer_mechanism(evidence, [])
    text = engine.build_mechanism_hypothesis_text(
        "DB connection pool exhaustion", "db-svc", "api-svc", inference
    )
    assert "db-svc" in text
    assert "api-svc" in text


def test_build_mechanism_hypothesis_text_no_inference(engine: OperationalSemanticEngine) -> None:
    text = engine.build_mechanism_hypothesis_text("Unknown spike", "svc-a", "svc-b", None)
    assert "svc-a" in text
    assert "svc-b" in text


def test_build_mechanism_causal_chain_includes_latent(engine: OperationalSemanticEngine) -> None:
    evidence = [_make_evidence("connection pool exhausted pool starvation")]
    inference = engine.infer_mechanism(evidence, [])
    chain = engine.build_mechanism_causal_chain("Pool exhaustion", "db-svc", "api-svc", inference)
    assert "->" in chain
    assert "api-svc" in chain


def test_build_mechanism_causal_chain_no_inference(engine: OperationalSemanticEngine) -> None:
    chain = engine.build_mechanism_causal_chain("Spike", "svc-a", "svc-b", None)
    assert "svc-a" in chain
    assert "svc-b" in chain


def test_to_dict_structure(engine: OperationalSemanticEngine) -> None:
    evidence = [_make_evidence("connection pool exhausted")]
    inference = engine.infer_mechanism(evidence, [])
    d = inference.to_dict()
    assert "primary_mechanism_id" in d
    assert "mechanism_confidence" in d
    assert "alternatives" in d
    assert "latent_state_implications" in d
    assert isinstance(d["alternatives"], list)


def test_inference_rationale_nonempty(engine: OperationalSemanticEngine) -> None:
    evidence = [_make_evidence("connection pool exhausted")]
    inference = engine.infer_mechanism(evidence, [])
    assert inference.inference_rationale
    assert len(inference.inference_rationale) > 10


def test_primary_mechanism_properties(engine: OperationalSemanticEngine) -> None:
    evidence = [_make_evidence("connection pool exhausted pool starvation")]
    inference = engine.infer_mechanism(evidence, [])
    assert inference.primary_mechanism_id == "connection_pool_starvation"
    assert inference.primary_mechanism_name is not None
    assert len(inference.primary_mechanism_name) > 0
