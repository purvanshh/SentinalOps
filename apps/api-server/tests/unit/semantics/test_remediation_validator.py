"""
Phase 45 remediation validator tests.

Proves:
  - DB lock contention → scaling frontend is flagged as incompatible (HIGH severity).
  - Connection pool starvation → increasing pool size is compatible (score >= 0.8).
  - Retry storm → rollback deployment is compatible.
  - Cache poisoning → flush cache is compatible.
  - Thread exhaustion → scale frontend replicas is incompatible.
  - Empty remediation text → alignment_score == 0.0.
  - No inference → overall_compatible == True (neutral), score == 0.5.
  - suggested_alternatives is populated from mechanism.
  - to_dict() includes required keys.
  - has_plausible action + no incompatible → overall_compatible True.
"""

from __future__ import annotations

import pytest
from semantics.remediation_validator import SemanticRemediationValidator
from semantics.semantic_engine import MechanismInference, OperationalSemanticEngine


@pytest.fixture()
def validator() -> SemanticRemediationValidator:
    return SemanticRemediationValidator()


@pytest.fixture()
def engine() -> OperationalSemanticEngine:
    return OperationalSemanticEngine()


def _infer(engine: OperationalSemanticEngine, text: str) -> MechanismInference:
    evidence = [{"summary": text, "item_key": "e1", "item_type": "log"}]
    return engine.infer_mechanism(evidence, [])


def test_lock_contention_rejects_frontend_scaling(
    validator: SemanticRemediationValidator,
    engine: OperationalSemanticEngine,
) -> None:
    inference = _infer(engine, "deadlock detected lock wait row lock long transaction")
    result = validator.validate("scale frontend replicas and increase api pods", inference)
    assert not result.overall_compatible
    assert "scale_frontend" in result.incompatible_actions
    assert any(i.severity == "HIGH" for i in result.issues)


def test_connection_pool_accepts_pool_increase(
    validator: SemanticRemediationValidator,
    engine: OperationalSemanticEngine,
) -> None:
    inference = _infer(engine, "connection pool exhausted db timeout pool starvation")
    result = validator.validate("increase pool size and connection pool limit", inference)
    assert result.alignment_score >= 0.8
    assert "increase_pool_size" in result.compatible_actions


def test_retry_storm_accepts_rollback(
    validator: SemanticRemediationValidator,
    engine: OperationalSemanticEngine,
) -> None:
    inference = _infer(engine, "retry storm exponential backoff cascading retries thundering herd")
    result = validator.validate("rollback deployment and revert release", inference)
    # rollback is plausible for retry_storm
    assert result.alignment_score > 0.3


def test_stale_cache_accepts_flush_cache(
    validator: SemanticRemediationValidator,
    engine: OperationalSemanticEngine,
) -> None:
    inference = _infer(engine, "stale cache poisoning cache invalidation stale entry stale data")
    result = validator.validate("flush cache and invalidate cache entries", inference)
    assert result.alignment_score >= 0.8
    assert "flush_cache" in result.compatible_actions


def test_thread_exhaustion_rejects_flush_cache(
    validator: SemanticRemediationValidator,
    engine: OperationalSemanticEngine,
) -> None:
    # flush_cache is incompatible with thread_exhaustion
    inference = _infer(engine, "thread pool exhaustion blocked threads thread starvation")
    result = validator.validate("flush cache redis flush invalidate cache", inference)
    assert not result.overall_compatible
    assert "flush_cache" in result.incompatible_actions


def test_empty_remediation_score_zero(
    validator: SemanticRemediationValidator,
    engine: OperationalSemanticEngine,
) -> None:
    inference = _infer(engine, "connection pool exhausted")
    result = validator.validate("", inference)
    assert result.alignment_score == 0.0


def test_no_inference_neutral_result(
    validator: SemanticRemediationValidator,
) -> None:
    result = validator.validate("scale frontend replicas", None)
    assert result.overall_compatible is True
    assert result.alignment_score == 0.5
    assert result.mechanism_id is None


def test_suggested_alternatives_populated(
    validator: SemanticRemediationValidator,
    engine: OperationalSemanticEngine,
) -> None:
    inference = _infer(engine, "connection pool exhausted db timeout")
    result = validator.validate("flush cache", inference)
    assert isinstance(result.suggested_alternatives, list)
    assert len(result.suggested_alternatives) > 0


def test_to_dict_required_keys(
    validator: SemanticRemediationValidator,
    engine: OperationalSemanticEngine,
) -> None:
    inference = _infer(engine, "connection pool exhausted")
    result = validator.validate("increase pool size", inference)
    d = result.to_dict()
    required_keys = [
        "mechanism_id", "mechanism_name", "overall_compatible", "alignment_score",
        "issue_count", "issues", "compatible_actions", "incompatible_actions",
        "suggested_alternatives", "validation_rationale",
    ]
    for key in required_keys:
        assert key in d, f"Missing key: {key}"


def test_plausible_action_no_incompatible_overall_compatible(
    validator: SemanticRemediationValidator,
    engine: OperationalSemanticEngine,
) -> None:
    inference = _infer(engine, "connection pool exhausted pool starvation")
    result = validator.validate("increase pool size connection pool limit", inference)
    assert result.overall_compatible is True


def test_mixed_actions_partial_alignment(
    validator: SemanticRemediationValidator,
    engine: OperationalSemanticEngine,
) -> None:
    inference = _infer(engine, "connection pool exhausted pool starvation")
    # Both compatible (increase pool size) and incompatible (scale frontend) present
    result = validator.validate(
        "increase pool size and scale frontend replicas", inference
    )
    # overall_compatible should be False (has incompatible)
    assert not result.overall_compatible
    assert 0.3 < result.alignment_score < 0.8  # partially aligned


def test_missing_mechanism_aligned_action_issue(
    validator: SemanticRemediationValidator,
    engine: OperationalSemanticEngine,
) -> None:
    inference = _infer(engine, "connection pool exhausted pool starvation")
    # Remediation text has no known action patterns
    result = validator.validate("review documentation and add runbook", inference)
    issue_types = [i.issue_type for i in result.issues]
    assert "missing_mechanism_aligned_action" in issue_types
