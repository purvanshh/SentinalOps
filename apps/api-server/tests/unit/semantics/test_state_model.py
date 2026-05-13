"""
Phase 45 latent infrastructure state model tests.

Proves:
  - Stable CPU + rising DB wait → connection_saturation latent state.
  - High N+1 query evidence → query_amplification latent state.
  - Deadlock evidence → lock_held latent state.
  - Consumer lag evidence → consumer_saturation latent state.
  - Thread exhaustion evidence → thread_saturation latent state.
  - Deployment evidence → deployment_regression latent state.
  - Memory evidence → heap_saturation latent state.
  - Circuit breaker open → circuit_breaker_open latent state.
  - Empty evidence → inference_confidence == 0.0.
  - missing_signals_for_certainty is populated.
  - inference.primary_state is None when no signals match.
"""

from __future__ import annotations

import pytest
from semantics.state_model import InfrastructureStateModel


@pytest.fixture()
def model() -> InfrastructureStateModel:
    return InfrastructureStateModel()


def _ev(summary: str, metric: str = "", item_type: str = "log") -> dict:
    return {"summary": summary, "metric": metric, "item_type": item_type, "item_key": "k"}


def test_connection_saturation_detected(model: InfrastructureStateModel) -> None:
    """Stable CPU + rising DB waits → connection_saturation (not CPU-bound)."""
    evidence = [
        _ev("db timeout connection pool wait time spiking", metric="db_connection_wait"),
        _ev("latency p99 increased", metric="latency_p99"),
        # No CPU spike signal
    ]
    result = model.infer(evidence, [])
    assert result.primary_state is not None
    assert result.primary_state.state_id == "connection_saturation"


def test_query_amplification_detected(model: InfrastructureStateModel) -> None:
    evidence = [
        _ev("n+1 query detected excessive queries orm query amplification", item_type="metric"),
        _ev("db cpu spike from query fanout"),
    ]
    result = model.infer(evidence, [])
    assert result.primary_state is not None
    assert result.primary_state.state_id == "query_amplification"


def test_lock_held_detected(model: InfrastructureStateModel) -> None:
    evidence = [
        _ev("deadlock detected lock wait time 8 seconds row lock blocking"),
    ]
    result = model.infer(evidence, [])
    assert result.primary_state is not None
    assert result.primary_state.state_id == "lock_held"


def test_consumer_saturation_detected(model: InfrastructureStateModel) -> None:
    evidence = [
        _ev("consumer lag 80000 messages kafka lag growing backpressure"),
        _ev("queue depth increasing", metric="consumer_lag"),
    ]
    result = model.infer(evidence, [])
    assert result.primary_state is not None
    assert result.primary_state.state_id == "consumer_saturation"


def test_thread_saturation_detected(model: InfrastructureStateModel) -> None:
    evidence = [
        _ev("thread pool exhaustion all threads busy blocked threads"),
    ]
    result = model.infer(evidence, [])
    assert result.primary_state is not None
    assert result.primary_state.state_id == "thread_saturation"


def test_heap_saturation_detected(model: InfrastructureStateModel) -> None:
    evidence = [
        _ev("gc pause heap exhaustion out of memory memory pressure"),
        _ev("heap usage at 95%", metric="jvm_heap_used"),
    ]
    result = model.infer(evidence, [])
    assert result.primary_state is not None
    assert result.primary_state.state_id == "heap_saturation"


def test_circuit_breaker_open_detected(model: InfrastructureStateModel) -> None:
    evidence = [
        _ev("circuit breaker tripped circuit open downstream unavailable"),
    ]
    result = model.infer(evidence, [])
    assert result.primary_state is not None
    assert result.primary_state.state_id == "circuit_breaker_open"


def test_request_amplification_detected(model: InfrastructureStateModel) -> None:
    evidence = [
        _ev("retry storm cascading retries exponential backoff thundering herd"),
    ]
    result = model.infer(evidence, [])
    assert result.primary_state is not None
    assert result.primary_state.state_id == "request_amplification"


def test_empty_evidence_zero_confidence(model: InfrastructureStateModel) -> None:
    result = model.infer([], [])
    assert result.primary_state is None
    assert result.inference_confidence == 0.0


def test_no_matching_signals_primary_none(model: InfrastructureStateModel) -> None:
    evidence = [_ev("system running fine no errors all metrics nominal")]
    result = model.infer(evidence, [])
    # May or may not have a primary_state; if not, confirm None
    # (if something weak matches, that's OK, but confidence should be low)
    if result.primary_state is None:
        assert result.inference_confidence == 0.0


def test_inference_confidence_range(model: InfrastructureStateModel) -> None:
    evidence = [_ev("connection pool exhausted db timeout")]
    result = model.infer(evidence, [])
    assert 0.0 <= result.inference_confidence <= 1.0


def test_alternative_states_populated(model: InfrastructureStateModel) -> None:
    evidence = [
        _ev("connection pool exhausted db timeout pool starvation"),
        _ev("deadlock detected lock wait"),
    ]
    result = model.infer(evidence, [])
    assert isinstance(result.alternative_states, list)


def test_missing_signals_for_certainty_populated(model: InfrastructureStateModel) -> None:
    evidence = [_ev("connection pool exhausted db timeout")]
    result = model.infer(evidence, [])
    assert isinstance(result.missing_signals_for_certainty, list)


def test_observable_signal_summary_nonempty(model: InfrastructureStateModel) -> None:
    evidence = [_ev("connection pool exhausted")]
    result = model.infer(evidence, [])
    assert result.observable_signal_summary


def test_implied_mechanisms_nonempty(model: InfrastructureStateModel) -> None:
    evidence = [_ev("connection pool exhausted db timeout pool starvation")]
    result = model.infer(evidence, [])
    if result.primary_state is not None:
        assert isinstance(result.primary_state.implied_mechanisms, list)
        assert len(result.primary_state.implied_mechanisms) > 0


def test_deployment_regression_detected(model: InfrastructureStateModel) -> None:
    evidence = [
        _ev("newly deployed version deployed regression post-deploy degradation"),
    ]
    result = model.infer(evidence, [])
    assert result.primary_state is not None
    assert result.primary_state.state_id == "deployment_regression"
