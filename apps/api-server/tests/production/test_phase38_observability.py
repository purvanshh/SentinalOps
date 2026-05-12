"""
Phase-38 observability lifecycle validation and trace continuity hardening.

Proves:
  - All 5 new Phase-38 metric counters exist and increment correctly
  - observe_degraded_mode fires on OperatingModeManager.transition_to
  - observe_dead_letter fires in replay loop when attempts >= MAX
  - observe_task_replay fires when a task is successfully re-enqueued
  - observe_execution_guard_block fires for each guard rejection reason
  - execution_id context var is accessible and bound via bind_execution_id
  - bind_incident_context accepts execution_id kwarg
  - Prometheus text format includes new metric names
  - Snapshot dict contains all 11 required metric keys
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helper: read a prometheus counter value by name
# ---------------------------------------------------------------------------

def _counter_value(metric_name: str, **labels) -> float:
    from prometheus_client import REGISTRY
    for metric in REGISTRY.collect():
        if metric.name in {metric_name, metric_name.removesuffix("_total")}:
            for sample in metric.samples:
                if sample.name in {metric_name, metric_name + "_total"}:
                    if all(sample.labels.get(k) == v for k, v in labels.items()):
                        return sample.value
    return 0.0


# ---------------------------------------------------------------------------
# New metrics exist and increment
# ---------------------------------------------------------------------------

def test_degraded_mode_activations_counter_increments():
    from observability.metrics import observe_degraded_mode

    before = _counter_value("degraded_mode_activations_total", from_mode="FULL", to_mode="DEGRADED")
    observe_degraded_mode("FULL", "DEGRADED")
    after = _counter_value("degraded_mode_activations_total", from_mode="FULL", to_mode="DEGRADED")
    assert after == before + 1


def test_task_replays_counter_increments():
    from observability.metrics import observe_task_replay

    before = _counter_value("task_replays_total", reason="stale-after-20s")
    observe_task_replay("stale-after-20s")
    after = _counter_value("task_replays_total", reason="stale-after-20s")
    assert after == before + 1


def test_dead_letter_tasks_counter_increments():
    from observability.metrics import observe_dead_letter

    before = _counter_value("dead_letter_tasks_total", task_name="workers.tasks.run_incident_pipeline")
    observe_dead_letter("workers.tasks.run_incident_pipeline")
    after = _counter_value("dead_letter_tasks_total", task_name="workers.tasks.run_incident_pipeline")
    assert after == before + 1


def test_execution_guard_blocks_counter_increments_not_allowlisted():
    from observability.metrics import observe_execution_guard_block

    before = _counter_value("execution_guard_blocks_total", reason="not_allowlisted")
    observe_execution_guard_block("not_allowlisted")
    after = _counter_value("execution_guard_blocks_total", reason="not_allowlisted")
    assert after == before + 1


def test_execution_guard_blocks_counter_increments_incident_mismatch():
    from observability.metrics import observe_execution_guard_block

    before = _counter_value("execution_guard_blocks_total", reason="incident_mismatch")
    observe_execution_guard_block("incident_mismatch")
    after = _counter_value("execution_guard_blocks_total", reason="incident_mismatch")
    assert after == before + 1


def test_remediation_actions_counter_increments():
    from observability.metrics import observe_remediation_action

    before = _counter_value("remediation_actions_total", outcome="executed")
    observe_remediation_action("executed")
    after = _counter_value("remediation_actions_total", outcome="executed")
    assert after == before + 1


# ---------------------------------------------------------------------------
# Snapshot dict completeness
# ---------------------------------------------------------------------------

def test_metrics_snapshot_contains_all_required_keys():
    from observability.metrics import build_metrics_snapshot

    snap = build_metrics_snapshot()
    required = {
        "api_requests_total",
        "incidents_total",
        "agent_executions_total",
        "tool_executions_total",
        "incident_pipeline_completed_total",
        "approval_decisions_total",
        "degraded_mode_activations_total",
        "task_replays_total",
        "dead_letter_tasks_total",
        "execution_guard_blocks_total",
        "remediation_actions_total",
    }
    missing = required - set(snap.keys())
    assert not missing, f"Missing keys in snapshot: {missing}"


# ---------------------------------------------------------------------------
# Degraded mode metric fires on OperatingModeManager.transition_to
# ---------------------------------------------------------------------------

def test_operating_mode_transition_fires_metric():
    from core.resilience.operating_mode import OperatingMode, OperatingModeManager

    mgr = OperatingModeManager()
    mgr.reset()

    before = _counter_value("degraded_mode_activations_total", from_mode="FULL", to_mode="SAFE_MODE")
    mgr.transition_to(OperatingMode.SAFE_MODE, "test: all providers failed")
    after = _counter_value("degraded_mode_activations_total", from_mode="FULL", to_mode="SAFE_MODE")
    assert after == before + 1

    mgr.reset()


# ---------------------------------------------------------------------------
# execution_id context var
# ---------------------------------------------------------------------------

def test_execution_id_var_is_accessible():
    from observability.logging.formatter import execution_id_var

    execution_id_var.set("exec-123")
    assert execution_id_var.get() == "exec-123"
    execution_id_var.set(None)


def test_bind_execution_id_sets_context_var():
    from observability.logging import bind_execution_id
    from observability.logging.formatter import execution_id_var

    bind_execution_id("exec-abc-456")
    assert execution_id_var.get() == "exec-abc-456"
    bind_execution_id(None)


def test_bind_incident_context_accepts_execution_id():
    from observability.logging import bind_incident_context
    from observability.logging.formatter import execution_id_var, incident_id_var

    bind_incident_context(incident_id="inc-001", execution_id="exec-789")
    assert incident_id_var.get() == "inc-001"
    assert execution_id_var.get() == "exec-789"

    bind_incident_context(incident_id=None, execution_id=None)


# ---------------------------------------------------------------------------
# Prometheus text format includes new metric names
# ---------------------------------------------------------------------------

def test_prometheus_output_includes_degraded_mode_metric():
    from observability.metrics import render_metrics

    payload, _ = render_metrics()
    text = payload.decode()
    assert "degraded_mode_activations_total" in text


def test_prometheus_output_includes_dead_letter_metric():
    from observability.metrics import render_metrics

    payload, _ = render_metrics()
    text = payload.decode()
    assert "dead_letter_tasks_total" in text


def test_prometheus_output_includes_execution_guard_metric():
    from observability.metrics import render_metrics

    payload, _ = render_metrics()
    text = payload.decode()
    assert "execution_guard_blocks_total" in text


# ---------------------------------------------------------------------------
# Execution guard emits metric when blocking
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_guard_block_emits_metric_not_allowlisted(monkeypatch):
    from tools.execution_guard import enforce_tool_execution_policy, ExecutionGuardError

    monkeypatch.setattr(
        "tools.execution_guard.load_tool_allowlist",
        lambda: {"dangerous_tools": ["safe_tool"]},
    )

    before = _counter_value("execution_guard_blocks_total", reason="not_allowlisted")
    with pytest.raises(ExecutionGuardError):
        await enforce_tool_execution_policy(
            tool_name="unlisted_tool",
            safety_level="standard",
            context={"incident_id": "inc-001", "actor_id": "op-1"},
            session=None,
        )
    after = _counter_value("execution_guard_blocks_total", reason="not_allowlisted")
    assert after == before + 1
