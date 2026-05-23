"""
Infrastructure State Model for SentinelOps Phase 45.

Infers hidden (latent) infrastructure states from observable evidence signals.
This is the core of semantic operational cognition: moving from
'these signals are present' to 'the infrastructure is probably in this state'.

Latent states are not directly observable. They must be inferred from the
combination of signals, their temporal ordering, and their operational context.

Example inference:
  Observed: rising latency, stable CPU, increasing DB waits
  Inferred: possible connection pool starvation OR lock contention
  → surfaced as probabilistic latent state hypotheses
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class LatentStateHypothesis:
    """A hypothesized hidden infrastructure state."""

    state_id: str
    state_name: str
    description: str
    probability: float
    supporting_signals: list[str]
    contradicting_signals: list[str]
    implied_mechanisms: list[str]
    recommended_investigations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "state_id": self.state_id,
            "state_name": self.state_name,
            "description": self.description,
            "probability": round(self.probability, 4),
            "supporting_signals": self.supporting_signals,
            "contradicting_signals": self.contradicting_signals,
            "implied_mechanisms": self.implied_mechanisms,
            "recommended_investigations": self.recommended_investigations,
        }


@dataclass
class LatentStateInference:
    """Result of latent infrastructure state inference."""

    primary_state: LatentStateHypothesis | None
    alternative_states: list[LatentStateHypothesis]
    observable_signal_summary: list[str]
    inference_confidence: float
    missing_signals_for_certainty: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "primary_state": self.primary_state.to_dict() if self.primary_state else None,
            "alternative_states": [s.to_dict() for s in self.alternative_states[:3]],
            "observable_signal_summary": self.observable_signal_summary,
            "inference_confidence": round(self.inference_confidence, 4),
            "missing_signals_for_certainty": self.missing_signals_for_certainty,
        }


# Latent state definitions: each entry maps a set of signal patterns
# to a latent infrastructure state with supporting/contradicting conditions.
_STATE_DEFINITIONS: list[dict[str, Any]] = [
    {
        "state_id": "connection_saturation",
        "state_name": "Connection Pool Near Saturation",
        "description": (
            "The database connection pool is at or near its limit. Requests are "
            "waiting for connections to become available."
        ),
        "positive_signals": [
            "db timeout",
            "connection wait",
            "pool",
            "connection limit",
            "acquisition latency",
            "connection queue",
        ],
        "negative_signals": ["cpu high", "disk io", "network timeout"],
        "neutral_signals": ["latency", "p99", "request queue"],
        "implied_mechanisms": ["connection_pool_starvation", "query_fanout_amplification"],
        "recommended_investigations": [
            "Check current active DB connections vs pool size limit.",
            "Identify queries holding connections longest.",
            "Review recent deployments for ORM or query changes.",
        ],
        "requires_stable_cpu": True,
        "base_weight": 1.0,
    },
    {
        "state_id": "query_amplification",
        "state_name": "Query Fanout Active",
        "description": (
            "Each application request is triggering more database queries than expected, "
            "potentially due to ORM lazy loading or missing join optimizations."
        ),
        "positive_signals": [
            "n+1",
            "n plus one",
            "query fanout",
            "orm",
            "excessive queries",
            "too many queries",
            "db cpu",
        ],
        "negative_signals": ["connection pool", "lock", "deadlock"],
        "neutral_signals": ["latency", "deployment"],
        "implied_mechanisms": ["query_fanout_amplification", "connection_pool_starvation"],
        "recommended_investigations": [
            "Enable slow query logging and identify high-frequency query patterns.",
            "Check ORM query counts per request in profiling.",
            "Review deployment for new ORM relationships without eager loading.",
        ],
        "requires_stable_cpu": False,
        "base_weight": 0.9,
    },
    {
        "state_id": "lock_held",
        "state_name": "Database Lock Held",
        "description": (
            "A long-running transaction or query is holding a lock that blocks "
            "concurrent writes. Other transactions are queued waiting for the lock."
        ),
        "positive_signals": [
            "lock",
            "deadlock",
            "lock wait",
            "lock contention",
            "serialization",
            "transaction block",
        ],
        "negative_signals": ["thread pool", "cache", "retry"],
        "neutral_signals": ["db", "latency", "connection"],
        "implied_mechanisms": ["lock_contention"],
        "recommended_investigations": [
            "Identify and kill long-running transactions.",
            "Check for missing database indexes causing full table scans.",
            "Review deployment for bulk operations in transactions.",
        ],
        "requires_stable_cpu": True,
        "base_weight": 1.1,
    },
    {
        "state_id": "consumer_saturation",
        "state_name": "Message Consumer Saturated",
        "description": (
            "Message consumers cannot process incoming messages fast enough. "
            "Queue depth is growing and consumer lag is increasing."
        ),
        "positive_signals": [
            "consumer lag",
            "kafka lag",
            "queue depth",
            "message backlog",
            "backpressure",
            "consumer behind",
        ],
        "negative_signals": ["db timeout", "connection pool", "thread pool"],
        "neutral_signals": ["latency", "deployment", "throughput"],
        "implied_mechanisms": ["queue_buildup_backpressure"],
        "recommended_investigations": [
            "Check consumer group lag metrics per partition.",
            "Review consumer throughput vs producer rate.",
            "Identify bottleneck in consumer processing pipeline.",
        ],
        "requires_stable_cpu": False,
        "base_weight": 0.9,
    },
    {
        "state_id": "thread_saturation",
        "state_name": "Thread Pool Saturated",
        "description": (
            "The application's thread pool is full. Incoming requests are queued "
            "waiting for free threads, typically because threads are blocked on I/O."
        ),
        "positive_signals": [
            "thread pool",
            "thread exhaustion",
            "thread starvation",
            "blocked threads",
            "executor queue",
            "thread limit",
        ],
        "negative_signals": ["cpu high", "connection pool", "consumer lag"],
        "neutral_signals": ["latency", "request queue"],
        "implied_mechanisms": ["thread_exhaustion", "slow_downstream_propagation"],
        "recommended_investigations": [
            "Check thread pool utilization and queue depth.",
            "Identify which I/O operations are blocking threads.",
            "Review downstream dependencies for increased latency.",
        ],
        "requires_stable_cpu": True,
        "base_weight": 0.9,
    },
    {
        "state_id": "deployment_regression",
        "state_name": "Deployment Regression Active",
        "description": (
            "A recent deployment is the probable cause. The temporal correlation between "
            "deployment event and degradation onset strongly suggests a code or config "
            "regression."
        ),
        "positive_signals": [
            "deployment",
            "deploy",
            "regression",
            "rollback",
            "post-deploy",
            "newly deployed",
            "release",
        ],
        "negative_signals": ["traffic spike", "noisy alert", "self-resolving"],
        "neutral_signals": ["latency", "error rate", "cpu"],
        "implied_mechanisms": [
            "deployment_induced_regression",
            "query_fanout_amplification",
            "connection_pool_starvation",
        ],
        "recommended_investigations": [
            "Correlate exact deployment timestamp with anomaly onset.",
            "Review deployment diff for query, ORM, or connection changes.",
            "Consider rollback if correlation is strong.",
        ],
        "requires_stable_cpu": False,
        "base_weight": 1.0,
    },
    {
        "state_id": "heap_saturation",
        "state_name": "Heap / Memory Near Exhaustion",
        "description": (
            "Available heap memory is near its limit. GC is running frequently, "
            "introducing latency spikes without proportional CPU increase."
        ),
        "positive_signals": [
            "memory",
            "heap",
            "gc pause",
            "oom",
            "out of memory",
            "garbage collection",
            "memory leak",
        ],
        "negative_signals": ["connection pool", "consumer lag", "lock"],
        "neutral_signals": ["latency", "cpu"],
        "implied_mechanisms": ["memory_pressure"],
        "recommended_investigations": [
            "Profile heap usage to identify large object allocations.",
            "Check GC pause frequency and duration.",
            "Review deployment for memory regression.",
        ],
        "requires_stable_cpu": True,
        "base_weight": 0.8,
    },
    {
        "state_id": "circuit_breaker_open",
        "state_name": "Circuit Breaker Open / Unstable",
        "description": (
            "A circuit breaker is open or oscillating. The protected dependency is "
            "unavailable or intermittently unavailable."
        ),
        "positive_signals": [
            "circuit breaker",
            "circuit open",
            "circuit tripped",
            "half open",
            "circuit flapping",
        ],
        "negative_signals": ["consumer lag", "thread pool", "connection pool"],
        "neutral_signals": ["dependency", "latency", "error rate"],
        "implied_mechanisms": ["circuit_breaker_instability", "dependency_collapse"],
        "recommended_investigations": [
            "Check circuit breaker state for protected dependencies.",
            "Review downstream service health metrics.",
            "Tune circuit breaker threshold if appropriate.",
        ],
        "requires_stable_cpu": False,
        "base_weight": 0.8,
    },
    {
        "state_id": "request_amplification",
        "state_name": "Request Amplification via Retries",
        "description": (
            "Client retries are amplifying request volume against a degraded service. "
            "The increased load prevents the service from recovering."
        ),
        "positive_signals": [
            "retry",
            "retry storm",
            "request amplification",
            "exponential backoff",
            "thundering herd",
            "cascading retries",
        ],
        "negative_signals": ["consumer lag", "thread pool", "lock"],
        "neutral_signals": ["latency", "error rate", "deployment"],
        "implied_mechanisms": ["retry_storm", "cascading_amplification"],
        "recommended_investigations": [
            "Measure client retry rate vs baseline request rate.",
            "Check circuit breaker configuration for affected clients.",
            "Verify jitter is present in retry backoff logic.",
        ],
        "requires_stable_cpu": False,
        "base_weight": 0.9,
    },
    {
        "state_id": "cache_cold_after_flush",
        "state_name": "Cache Cold After Flush or Invalidation",
        "description": (
            "The cache was recently flushed, invalidated, or deployed without "
            "warm-up. All requests are falling through to the backend until "
            "the cache warms up."
        ),
        "positive_signals": [
            "cache miss",
            "cache cold",
            "cache flush",
            "cache invalidation",
            "cache hit rate low",
        ],
        "negative_signals": ["connection pool", "thread pool", "consumer lag"],
        "neutral_signals": ["latency", "backend load"],
        "implied_mechanisms": ["stale_cache_poisoning", "deployment_induced_regression"],
        "recommended_investigations": [
            "Check cache hit rate trend over the past hour.",
            "Verify cache warm-up strategy after deployment.",
            "Review recent cache flush operations.",
        ],
        "requires_stable_cpu": False,
        "base_weight": 0.7,
    },
]


def _score_state(
    state_def: dict[str, Any],
    signal_text: str,
    has_stable_cpu: bool,
) -> float:
    lower = signal_text.lower()

    positive_score = sum(1 for sig in state_def["positive_signals"] if sig in lower)
    negative_score = sum(1 for sig in state_def["negative_signals"] if sig in lower)
    neutral_score = sum(0.3 for sig in state_def["neutral_signals"] if sig in lower)

    raw = state_def["base_weight"] * (positive_score + neutral_score - 0.5 * negative_score)

    # CPU-stability bonus: some states are more likely when CPU is stable
    if state_def.get("requires_stable_cpu") and has_stable_cpu:
        raw += 0.5

    return max(0.0, raw)


def _has_stable_cpu(evidence_items: list[dict[str, Any]]) -> bool:
    """
    Heuristic: CPU is stable if no evidence item mentions high CPU
    and at least one item mentions latency or connection issues.
    """
    combined = " ".join(
        str(v)
        for item in evidence_items
        for k, v in item.items()
        if k in ("summary", "metric", "description")
    ).lower()
    high_cpu_signals = ("cpu high", "cpu spike", "cpu utilization high", "cpu saturated")
    latency_signals = ("latency", "timeout", "wait", "slow")
    has_cpu_signal = any(sig in combined for sig in high_cpu_signals)
    has_latency_signal = any(sig in combined for sig in latency_signals)
    return has_latency_signal and not has_cpu_signal


def _normalize_scores(scores: list[float]) -> list[float]:
    total = sum(scores)
    if total <= 0:
        return [0.0] * len(scores)
    return [s / total for s in scores]


class InfrastructureStateModel:
    """
    Infers latent (hidden) infrastructure states from observable evidence.

    Produces probabilistic hypotheses about what hidden infrastructure
    conditions best explain the observed signals. This is the mechanism
    that transforms surface observations into operational understanding.
    """

    def infer(
        self,
        evidence_items: list[dict[str, Any]],
        timed_events: list[Any],
    ) -> LatentStateInference:
        signal_text = _build_signal_text(evidence_items, timed_events)
        stable_cpu = _has_stable_cpu(evidence_items)
        observable_summary = _build_observable_summary(evidence_items, timed_events)

        raw_scores = [
            _score_state(state_def, signal_text, stable_cpu) for state_def in _STATE_DEFINITIONS
        ]
        normalized = _normalize_scores(raw_scores)

        hypotheses: list[LatentStateHypothesis] = []
        for index, state_def in enumerate(_STATE_DEFINITIONS):
            prob = normalized[index]
            if prob < 0.03:
                continue
            matched_positive = [
                sig for sig in state_def["positive_signals"] if sig in signal_text.lower()
            ]
            contradicting = [
                sig for sig in state_def["negative_signals"] if sig in signal_text.lower()
            ]
            hypotheses.append(
                LatentStateHypothesis(
                    state_id=state_def["state_id"],
                    state_name=state_def["state_name"],
                    description=state_def["description"],
                    probability=round(prob, 4),
                    supporting_signals=matched_positive[:5],
                    contradicting_signals=contradicting[:3],
                    implied_mechanisms=list(state_def["implied_mechanisms"]),
                    recommended_investigations=list(state_def["recommended_investigations"]),
                )
            )

        hypotheses.sort(key=lambda h: h.probability, reverse=True)

        primary = hypotheses[0] if hypotheses else None
        alternatives = hypotheses[1:] if len(hypotheses) > 1 else []

        # Inference confidence: gap between top two states
        if len(hypotheses) >= 2:
            confidence = hypotheses[0].probability - hypotheses[1].probability
        elif hypotheses:
            confidence = hypotheses[0].probability
        else:
            confidence = 0.0

        # What additional signals would help narrow down the state?
        missing_signals = _missing_signals_for_certainty(primary, signal_text)

        return LatentStateInference(
            primary_state=primary,
            alternative_states=alternatives,
            observable_signal_summary=observable_summary,
            inference_confidence=round(min(confidence, 1.0), 4),
            missing_signals_for_certainty=missing_signals,
        )


def _build_signal_text(evidence_items: list[dict[str, Any]], timed_events: list[Any]) -> str:
    parts: list[str] = []
    for item in evidence_items:
        for key in ("summary", "metric", "signature", "description", "item_type"):
            val = item.get(key)
            if val:
                parts.append(str(val))
    for event in timed_events:
        summary = getattr(event, "summary", "") or ""
        if summary:
            parts.append(summary)
    return " ".join(parts)


def _build_observable_summary(
    evidence_items: list[dict[str, Any]], timed_events: list[Any]
) -> list[str]:
    summaries: list[str] = []
    for item in evidence_items:
        item_type = item.get("item_type", "")
        metric = item.get("metric", "")
        sig = item.get("signature", "")
        summary = item.get("summary", "")
        if metric:
            summaries.append(f"{item_type}: {metric}")
        elif sig:
            summaries.append(f"{item_type}: {sig}")
        elif summary:
            summaries.append(summary[:80])
    for event in timed_events:
        ev_summary = getattr(event, "summary", "") or ""
        if ev_summary:
            summaries.append(ev_summary[:80])
    return summaries[:10]


def _missing_signals_for_certainty(
    primary: LatentStateHypothesis | None, signal_text: str
) -> list[str]:
    if primary is None:
        return ["metrics telemetry", "database wait times", "deployment event log"]
    state_id = primary.state_id
    signal_map: dict[str, list[str]] = {
        "connection_saturation": [
            "current active connection count vs pool limit",
            "per-query connection hold time",
        ],
        "query_amplification": [
            "query count per request",
            "ORM query log",
        ],
        "lock_held": [
            "pg_locks or equivalent query output",
            "long-running transaction list",
        ],
        "consumer_saturation": [
            "per-partition consumer lag",
            "consumer processing time per message",
        ],
        "thread_saturation": [
            "thread pool utilization percentage",
            "which I/O call is blocking threads",
        ],
        "deployment_regression": [
            "exact deployment timestamp vs anomaly onset",
            "deployment diff",
        ],
        "heap_saturation": [
            "heap usage time series",
            "GC pause duration distribution",
        ],
        "circuit_breaker_open": [
            "circuit breaker state log for each dependency",
            "downstream service health metrics",
        ],
        "request_amplification": [
            "client retry count per second",
            "whether jitter is configured in retry logic",
        ],
        "cache_cold_after_flush": [
            "cache hit rate time series",
            "recent cache flush or invalidation events",
        ],
    }
    return signal_map.get(state_id, ["additional telemetry needed to confirm state"])
