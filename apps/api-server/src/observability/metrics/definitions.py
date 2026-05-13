from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

API_REQUESTS_TOTAL = Counter(
    "api_requests_total",
    "Total API requests handled by SentinelOps",
    labelnames=("method", "route"),
)
INCIDENTS_TOTAL = Counter(
    "incidents_total",
    "Total incidents created",
    labelnames=("source",),
)
AGENT_EXECUTIONS_TOTAL = Counter(
    "agent_executions_total",
    "Total agent executions",
    labelnames=("agent", "status"),
)
TOOL_EXECUTIONS_TOTAL = Counter(
    "tool_executions_total",
    "Total tool executions",
    labelnames=("tool", "outcome"),
)
AGENT_DURATION_SECONDS = Histogram(
    "agent_duration_seconds",
    "Agent execution duration in seconds",
    labelnames=("agent",),
)
APPROVAL_WAIT_SECONDS = Histogram(
    "approval_wait_seconds",
    "Approval wait time in seconds",
    labelnames=("status",),
)
INCIDENT_PIPELINE_COMPLETED_TOTAL = Counter(
    "incident_pipeline_completed_total",
    "Total incident pipelines that completed (success or failure)",
    labelnames=("status",),
)
INCIDENT_PIPELINE_DURATION_SECONDS = Histogram(
    "incident_pipeline_duration_seconds",
    "End-to-end incident pipeline duration in seconds",
    labelnames=("status",),
    buckets=(5, 10, 30, 60, 120, 300, 600),
)
APPROVAL_DECISIONS_TOTAL = Counter(
    "approval_decisions_total",
    "Total approval decisions recorded",
    labelnames=("decision",),
)

# --- Phase-38: operational runtime metrics ---

DEGRADED_MODE_ACTIVATIONS_TOTAL = Counter(
    "degraded_mode_activations_total",
    "Total operating-mode transitions (tracks every mode change, including recoveries)",
    labelnames=("from_mode", "to_mode"),
)
TASK_REPLAYS_TOTAL = Counter(
    "task_replays_total",
    "Total incident pipeline tasks re-enqueued by the replay scheduler",
    labelnames=("reason",),
)
DEAD_LETTER_TASKS_TOTAL = Counter(
    "dead_letter_tasks_total",
    "Total tasks moved to dead-letter after exhausting replay attempts",
    labelnames=("task_name",),
)
EXECUTION_GUARD_BLOCKS_TOTAL = Counter(
    "execution_guard_blocks_total",
    "Total tool executions blocked by the execution guard",
    labelnames=("reason",),
)
REMEDIATION_ACTIONS_TOTAL = Counter(
    "remediation_actions_total",
    "Total remediation actions attempted",
    labelnames=("outcome",),
)
CONFIDENCE_RELIABILITY = Histogram(
    "confidence_reliability",
    "Observed confidence reliability for probabilistic reasoning outputs",
    labelnames=("component",),
    buckets=(0.0, 0.25, 0.5, 0.65, 0.75, 0.85, 0.95, 1.0),
)
CALIBRATION_ERROR = Histogram(
    "calibration_error",
    "Observed calibration error for confidence-producing components",
    labelnames=("component",),
    buckets=(0.0, 0.02, 0.05, 0.1, 0.15, 0.25, 0.4, 1.0),
)
UNCERTAINTY_QUALITY = Histogram(
    "uncertainty_quality",
    "Quality of uncertainty estimates emitted by the reasoning engine",
    labelnames=("component",),
    buckets=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0),
)
ESCALATION_APPROPRIATENESS = Counter(
    "escalation_appropriateness_total",
    "Escalation recommendations emitted by uncertainty-aware reasoning",
    labelnames=("decision", "reason"),
)
OPERATOR_OVERRIDES_TOTAL = Counter(
    "operator_overrides_total",
    "Operator overrides observed after AI recommendations",
    labelnames=("component", "outcome"),
)
HYPOTHESIS_STABILITY = Histogram(
    "hypothesis_stability",
    "Stability margin between leading competing hypotheses",
    labelnames=("component",),
    buckets=(0.0, 0.05, 0.1, 0.2, 0.35, 0.5, 1.0),
)
CONTRADICTIONS_TOTAL = Counter(
    "contradictions_total",
    "Contradictions detected while reasoning about incidents",
    labelnames=("category",),
)

_METRIC_SNAPSHOT: dict[str, float] = {
    "api_requests_total": 0.0,
    "incidents_total": 0.0,
    "agent_executions_total": 0.0,
    "tool_executions_total": 0.0,
    "incident_pipeline_completed_total": 0.0,
    "approval_decisions_total": 0.0,
    "degraded_mode_activations_total": 0.0,
    "task_replays_total": 0.0,
    "dead_letter_tasks_total": 0.0,
    "execution_guard_blocks_total": 0.0,
    "remediation_actions_total": 0.0,
    "escalation_appropriateness_total": 0.0,
    "operator_overrides_total": 0.0,
    "contradictions_total": 0.0,
}


def observe_api_request(method: str, route: str) -> None:
    API_REQUESTS_TOTAL.labels(method=method, route=route).inc()
    _METRIC_SNAPSHOT["api_requests_total"] += 1


def observe_incident_created(source: str) -> None:
    INCIDENTS_TOTAL.labels(source=source).inc()
    _METRIC_SNAPSHOT["incidents_total"] += 1


def observe_agent_execution(agent: str, status: str, latency: float | None = None) -> None:
    AGENT_EXECUTIONS_TOTAL.labels(agent=agent, status=status).inc()
    _METRIC_SNAPSHOT["agent_executions_total"] += 1
    if latency is not None:
        AGENT_DURATION_SECONDS.labels(agent=agent).observe(latency)


def observe_tool_execution(tool: str, outcome: str) -> None:
    TOOL_EXECUTIONS_TOTAL.labels(tool=tool, outcome=outcome).inc()
    _METRIC_SNAPSHOT["tool_executions_total"] += 1


def observe_approval_wait(seconds: float, status: str) -> None:
    APPROVAL_WAIT_SECONDS.labels(status=status).observe(seconds)


def observe_pipeline_completed(status: str, duration_seconds: float | None = None) -> None:
    INCIDENT_PIPELINE_COMPLETED_TOTAL.labels(status=status).inc()
    _METRIC_SNAPSHOT["incident_pipeline_completed_total"] += 1
    if duration_seconds is not None:
        INCIDENT_PIPELINE_DURATION_SECONDS.labels(status=status).observe(duration_seconds)


def observe_approval_decision(decision: str) -> None:
    APPROVAL_DECISIONS_TOTAL.labels(decision=decision).inc()
    _METRIC_SNAPSHOT["approval_decisions_total"] += 1


def observe_degraded_mode(from_mode: str, to_mode: str) -> None:
    DEGRADED_MODE_ACTIVATIONS_TOTAL.labels(from_mode=from_mode, to_mode=to_mode).inc()
    _METRIC_SNAPSHOT["degraded_mode_activations_total"] += 1


def observe_task_replay(reason: str) -> None:
    TASK_REPLAYS_TOTAL.labels(reason=reason).inc()
    _METRIC_SNAPSHOT["task_replays_total"] += 1


def observe_dead_letter(task_name: str) -> None:
    DEAD_LETTER_TASKS_TOTAL.labels(task_name=task_name).inc()
    _METRIC_SNAPSHOT["dead_letter_tasks_total"] += 1


def observe_execution_guard_block(reason: str) -> None:
    EXECUTION_GUARD_BLOCKS_TOTAL.labels(reason=reason).inc()
    _METRIC_SNAPSHOT["execution_guard_blocks_total"] += 1


def observe_remediation_action(outcome: str) -> None:
    REMEDIATION_ACTIONS_TOTAL.labels(outcome=outcome).inc()
    _METRIC_SNAPSHOT["remediation_actions_total"] += 1


def observe_confidence_reliability(component: str, reliability: float) -> None:
    CONFIDENCE_RELIABILITY.labels(component=component).observe(reliability)


def observe_calibration_error(component: str, error: float) -> None:
    CALIBRATION_ERROR.labels(component=component).observe(error)


def observe_uncertainty_quality(component: str, quality: float) -> None:
    UNCERTAINTY_QUALITY.labels(component=component).observe(quality)


def observe_escalation_appropriateness(decision: str, reason: str) -> None:
    ESCALATION_APPROPRIATENESS.labels(decision=decision, reason=reason).inc()
    _METRIC_SNAPSHOT["escalation_appropriateness_total"] += 1


def observe_operator_override(component: str, outcome: str) -> None:
    OPERATOR_OVERRIDES_TOTAL.labels(component=component, outcome=outcome).inc()
    _METRIC_SNAPSHOT["operator_overrides_total"] += 1


def observe_hypothesis_stability(component: str, stability: float) -> None:
    HYPOTHESIS_STABILITY.labels(component=component).observe(stability)


def observe_contradiction(category: str) -> None:
    CONTRADICTIONS_TOTAL.labels(category=category).inc()
    _METRIC_SNAPSHOT["contradictions_total"] += 1


def build_metrics_snapshot() -> dict[str, float]:
    return dict(_METRIC_SNAPSHOT)


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
