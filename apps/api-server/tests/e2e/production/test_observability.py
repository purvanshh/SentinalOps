"""
Observability validation tests.

Proves:
  - Prometheus counters and histograms increment correctly
  - Pipeline lifecycle metrics are emitted
  - Approval decision metrics are emitted
  - Metrics snapshot tracks cumulative counts
  - Prometheus exposition format is valid
  - Structured log context vars inject incident fields
  - Tracing provider initialises without error
"""

from __future__ import annotations

from prometheus_client import REGISTRY

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _counter_value(metric_name: str, **labels) -> float:
    """Read the current value of a Prometheus counter or histogram count sample.

    prometheus_client appends '_total' to Counter samples regardless of
    whether the family name already ends in '_total'. We search both the
    given name and the name with '_total' appended.
    """
    candidates = {metric_name, metric_name + "_total"}
    for metric in REGISTRY.collect():
        for sample in metric.samples:
            if sample.name in candidates:
                if all(sample.labels.get(k) == v for k, v in labels.items()):
                    return sample.value
    return 0.0


# ---------------------------------------------------------------------------
# API request counter
# ---------------------------------------------------------------------------


def test_observe_api_request_increments_counter():
    from observability.metrics import observe_api_request

    before = _counter_value("api_requests_total", method="GET", route="/test-obs")
    observe_api_request("GET", "/test-obs")
    after = _counter_value("api_requests_total", method="GET", route="/test-obs")
    assert after == before + 1


# ---------------------------------------------------------------------------
# Incident created counter
# ---------------------------------------------------------------------------


def test_observe_incident_created_increments_counter():
    from observability.metrics import observe_incident_created

    before = _counter_value("incidents_total", source="pagerduty")
    observe_incident_created("pagerduty")
    after = _counter_value("incidents_total", source="pagerduty")
    assert after == before + 1


# ---------------------------------------------------------------------------
# Agent execution counter and histogram
# ---------------------------------------------------------------------------


def test_observe_agent_execution_increments_counter():
    from observability.metrics import observe_agent_execution

    before = _counter_value("agent_executions_total", agent="rootcause", status="completed")
    observe_agent_execution("rootcause", "completed")
    after = _counter_value("agent_executions_total", agent="rootcause", status="completed")
    assert after == before + 1


def test_observe_agent_execution_records_histogram_when_latency_provided():
    from observability.metrics import observe_agent_execution

    # Histogram count sample is named '{family}_count'
    before_count = _counter_value("agent_duration_seconds_count", agent="risk-hist")
    observe_agent_execution("risk-hist", "completed", latency=1.5)
    after_count = _counter_value("agent_duration_seconds_count", agent="risk-hist")
    assert after_count == before_count + 1


# ---------------------------------------------------------------------------
# Pipeline lifecycle metrics (new)
# ---------------------------------------------------------------------------


def test_observe_pipeline_completed_increments_counter():
    from observability.metrics import observe_pipeline_completed

    before = _counter_value("incident_pipeline_completed_total", status="resolved")
    observe_pipeline_completed("resolved")
    after = _counter_value("incident_pipeline_completed_total", status="resolved")
    assert after == before + 1


def test_observe_pipeline_completed_records_duration():
    from observability.metrics import observe_pipeline_completed

    # Use unique label value to avoid cross-test pollution
    before = _counter_value("incident_pipeline_duration_seconds_count", status="resolved-dur")
    observe_pipeline_completed("resolved-dur", duration_seconds=45.2)
    after = _counter_value("incident_pipeline_duration_seconds_count", status="resolved-dur")
    assert after == before + 1


def test_observe_pipeline_completed_no_duration_does_not_crash():
    from observability.metrics import observe_pipeline_completed

    observe_pipeline_completed("failed")  # no duration_seconds


# ---------------------------------------------------------------------------
# Approval decision metrics (new)
# ---------------------------------------------------------------------------


def test_observe_approval_decision_increments_approved_counter():
    from observability.metrics import observe_approval_decision

    before = _counter_value("approval_decisions_total", decision="approved")
    observe_approval_decision("approved")
    after = _counter_value("approval_decisions_total", decision="approved")
    assert after == before + 1


def test_observe_approval_decision_increments_rejected_counter():
    from observability.metrics import observe_approval_decision

    before = _counter_value("approval_decisions_total", decision="rejected")
    observe_approval_decision("rejected")
    after = _counter_value("approval_decisions_total", decision="rejected")
    assert after == before + 1


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------


def test_metrics_snapshot_includes_all_required_keys():
    from observability.metrics import build_metrics_snapshot

    snapshot = build_metrics_snapshot()
    required = {
        "api_requests_total",
        "incidents_total",
        "agent_executions_total",
        "tool_executions_total",
        "incident_pipeline_completed_total",
        "approval_decisions_total",
    }
    missing = required - snapshot.keys()
    assert not missing, f"Snapshot missing keys: {missing}"


def test_metrics_snapshot_increments_with_observations():
    from observability.metrics import build_metrics_snapshot, observe_incident_created

    before = build_metrics_snapshot()["incidents_total"]
    observe_incident_created("test-source")
    after = build_metrics_snapshot()["incidents_total"]
    assert after == before + 1


# ---------------------------------------------------------------------------
# Prometheus exposition format
# ---------------------------------------------------------------------------


def test_render_metrics_returns_bytes_and_content_type():
    from observability.metrics import render_metrics

    payload, content_type = render_metrics()
    assert isinstance(payload, bytes)
    assert "text/plain" in content_type


def test_render_metrics_contains_all_metric_names():
    from observability.metrics import render_metrics

    payload, _ = render_metrics()
    text = payload.decode()
    for metric_name in [
        "api_requests_total",
        "incidents_total",
        "agent_executions_total",
        "incident_pipeline_completed_total",
        "approval_decisions_total",
    ]:
        assert metric_name in text, f"Metric '{metric_name}' missing from /metrics output"


# ---------------------------------------------------------------------------
# Structured log context injection
# ---------------------------------------------------------------------------


def test_bind_incident_context_sets_context_vars():
    from observability.logging.formatter import (
        agent_var,
        bind_incident_context,
        incident_id_var,
        thread_id_var,
    )

    bind_incident_context(incident_id="inc-123", thread_id="thr-456", agent="router")
    assert incident_id_var.get() == "inc-123"
    assert thread_id_var.get() == "thr-456"
    assert agent_var.get() == "router"


def test_bind_request_id_sets_context_var():
    from observability.logging.formatter import bind_request_id, request_id_var

    bind_request_id("req-789")
    assert request_id_var.get() == "req-789"


# ---------------------------------------------------------------------------
# Tracing provider
# ---------------------------------------------------------------------------


def test_configure_tracing_does_not_raise():
    from observability.tracing import configure_tracing
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider

    configure_tracing()
    assert isinstance(trace.get_tracer_provider(), TracerProvider)


def test_get_tracer_returns_tracer():
    from observability.tracing import get_tracer

    tracer = get_tracer("test-service")
    assert tracer is not None
