"""
Failure Mechanism Ontology for SentinelOps Phase 45.

Models 15 operational failure mechanisms as structured concepts.
Each mechanism captures:
  - observable symptom signals
  - lexical keywords that suggest it
  - common causes
  - plausible remediations
  - incompatible remediations (what will NOT solve it)
  - latent infrastructure states it implies

This ontology drives:
  - root-cause ranking via mechanism plausibility scoring
  - remediation alignment validation
  - hallucination detection via mechanism coherence checks
  - semantic hypothesis generation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FailureMechanism:
    mechanism_id: str
    name: str
    description: str
    symptom_signals: tuple[str, ...]
    symptom_keywords: tuple[str, ...]
    common_causes: tuple[str, ...]
    plausible_remediations: tuple[str, ...]
    incompatible_remediations: tuple[str, ...]
    latent_states: tuple[str, ...]
    severity_amplifiers: tuple[str, ...] = field(default_factory=tuple)

    def matches_keywords(self, text: str) -> int:
        lower = text.lower()
        return sum(1 for kw in self.symptom_keywords if kw in lower)

    def is_remediation_compatible(self, remediation_text: str) -> tuple[bool, str]:
        lower = remediation_text.lower()
        for incompatible in self.incompatible_remediations:
            if incompatible.lower() in lower:
                return False, (
                    f"'{incompatible}' does not address the inferred mechanism "
                    f"'{self.name}' and may be counterproductive."
                )
        return True, ""


_MECHANISMS: list[FailureMechanism] = [
    FailureMechanism(
        mechanism_id="connection_pool_starvation",
        name="Connection Pool Starvation",
        description=(
            "The database connection pool is exhausted. Incoming requests queue behind a "
            "depleted pool, causing rising p99 latency and timeouts while CPU stays stable."
        ),
        symptom_signals=(
            "db_connection_wait", "pool_exhaustion", "connection_timeout",
            "connection_acquisition_latency", "db_pool_size",
        ),
        symptom_keywords=(
            "connection pool", "pool exhausted", "db timeout", "connection wait",
            "acquisition latency", "connection limit", "pool starvation",
            "db connections", "connection queue", "waiting for connection",
        ),
        common_causes=(
            "deployment_regression", "missing_index_causing_long_queries",
            "traffic_spike", "query_fanout_amplification", "slow_queries_holding_connections",
        ),
        plausible_remediations=(
            "rollback_deployment", "add_database_index", "increase_pool_size",
            "kill_long_running_queries", "scale_read_replicas", "restart_service",
        ),
        incompatible_remediations=(
            "scale_frontend", "increase_frontend_replicas", "increase_cache_size",
            "flush_cache", "restart_load_balancer",
        ),
        latent_states=(
            "connection_saturation", "query_amplification", "long_query_lock",
        ),
    ),
    FailureMechanism(
        mechanism_id="retry_storm",
        name="Retry Storm",
        description=(
            "Failing requests are retried aggressively by clients or intermediaries, "
            "producing a positive feedback loop that amplifies load on the degraded "
            "service and prevents recovery."
        ),
        symptom_signals=(
            "request_rate_spike", "error_rate_high", "upstream_retry_count",
            "client_retry_amplification",
        ),
        symptom_keywords=(
            "retry", "retry storm", "exponential backoff", "retry amplification",
            "request amplification", "cascade retries", "retry loop",
            "thundering herd", "client retrying",
        ),
        common_causes=(
            "downstream_service_degradation", "timeout_configuration_too_short",
            "missing_circuit_breaker", "deployment_regression",
        ),
        plausible_remediations=(
            "enable_circuit_breaker", "increase_timeout", "shed_load",
            "rollback_deployment", "rate_limit_clients", "add_jitter_to_retry",
        ),
        incompatible_remediations=(
            "add_database_index", "scale_database", "increase_pool_size",
            "flush_cache",
        ),
        latent_states=(
            "request_amplification", "circuit_breaker_open", "overload_propagation",
        ),
    ),
    FailureMechanism(
        mechanism_id="queue_buildup_backpressure",
        name="Queue Buildup / Backpressure",
        description=(
            "Consumers cannot keep up with producers. Messages queue behind slow consumers, "
            "causing consumer lag, rising queue depth, and eventual producer backpressure "
            "or dropped messages."
        ),
        symptom_signals=(
            "consumer_lag", "queue_depth", "message_processing_time",
            "producer_backpressure", "kafka_lag", "rabbitmq_depth",
        ),
        symptom_keywords=(
            "consumer lag", "queue depth", "backpressure", "message lag",
            "kafka lag", "queue buildup", "slow consumer", "message backlog",
            "producer blocked", "queue overflow",
        ),
        common_causes=(
            "slow_consumer_processing", "consumer_deployment_regression",
            "downstream_dependency_slow", "traffic_spike_in_producer",
        ),
        plausible_remediations=(
            "scale_consumers", "rollback_consumer_deployment", "increase_consumer_threads",
            "optimize_consumer_processing", "shed_producer_load",
        ),
        incompatible_remediations=(
            "scale_frontend", "add_database_index", "increase_pool_size",
            "restart_load_balancer",
        ),
        latent_states=(
            "consumer_saturation", "queue_pressure", "processing_bottleneck",
        ),
    ),
    FailureMechanism(
        mechanism_id="lock_contention",
        name="Lock Contention",
        description=(
            "Long-running transactions or heavy row-level locking is blocking concurrent "
            "database writes. Other transactions queue behind the lock holder, causing "
            "rising latency while throughput drops."
        ),
        symptom_signals=(
            "lock_wait_time", "serialization_errors", "deadlock_count",
            "transaction_wait", "db_lock_waits",
        ),
        symptom_keywords=(
            "lock", "deadlock", "lock wait", "lock contention", "lock timeout",
            "serialization failure", "row lock", "table lock", "transaction block",
            "lock holder", "long transaction",
        ),
        common_causes=(
            "missing_index_causing_full_table_scans", "deployment_regression",
            "bulk_operation_in_transaction", "missing_transaction_timeout",
        ),
        plausible_remediations=(
            "add_database_index", "kill_long_running_queries", "reduce_transaction_scope",
            "rollback_deployment", "add_transaction_timeout",
        ),
        incompatible_remediations=(
            "scale_frontend", "increase_cache_size", "flush_cache",
            "scale_consumers", "restart_load_balancer",
        ),
        latent_states=(
            "lock_held", "transaction_queue", "write_serialization_bottleneck",
        ),
    ),
    FailureMechanism(
        mechanism_id="stale_cache_poisoning",
        name="Stale Cache Poisoning",
        description=(
            "Cached values contain stale or incorrect data. High cache hit rates conceal "
            "the underlying data staleness, causing silent corruption or incorrect "
            "responses without obvious error signals."
        ),
        symptom_signals=(
            "incorrect_response", "stale_data_served", "cache_hit_rate",
            "data_inconsistency",
        ),
        symptom_keywords=(
            "stale cache", "cache poison", "cache invalidation", "stale data",
            "cache corruption", "incorrect cached", "cache miss after", "stale entry",
            "cache inconsistency",
        ),
        common_causes=(
            "deployment_changed_data_format", "missing_cache_invalidation",
            "cache_key_collision", "long_ttl_with_schema_change",
        ),
        plausible_remediations=(
            "flush_cache", "invalidate_cache_keys", "rollback_deployment",
            "reduce_cache_ttl", "add_cache_versioning",
        ),
        incompatible_remediations=(
            "scale_frontend", "increase_pool_size", "add_database_index",
            "scale_consumers", "restart_database",
        ),
        latent_states=(
            "cache_cold_after_flush", "stale_ttl_active", "deployment_format_mismatch",
        ),
    ),
    FailureMechanism(
        mechanism_id="thread_exhaustion",
        name="Thread Exhaustion",
        description=(
            "The application's thread pool is saturated. Incoming requests queue waiting "
            "for a free thread. CPU may appear normal because threads are blocked on I/O "
            "rather than actively computing."
        ),
        symptom_signals=(
            "thread_pool_full", "request_queue_depth", "thread_wait_time",
            "active_thread_count",
        ),
        symptom_keywords=(
            "thread pool", "thread exhaustion", "thread starvation", "blocked threads",
            "thread queue", "active threads", "thread limit", "thread busy",
            "executor queue", "thread saturation",
        ),
        common_causes=(
            "slow_downstream_blocking_threads", "synchronous_io_in_thread",
            "thread_pool_misconfiguration", "traffic_spike",
        ),
        plausible_remediations=(
            "increase_thread_pool_size", "make_io_async", "scale_service",
            "rollback_deployment", "shed_load",
        ),
        incompatible_remediations=(
            "add_database_index", "increase_pool_size", "flush_cache",
            "scale_consumers",
        ),
        latent_states=(
            "thread_saturation", "blocking_io_bottleneck", "request_queue_pressure",
        ),
    ),
    FailureMechanism(
        mechanism_id="deployment_induced_regression",
        name="Deployment-Induced Regression",
        description=(
            "A recent deployment introduced a regression that degraded performance or "
            "correctness. The temporal correlation between deployment and anomaly onset "
            "is the primary diagnostic signal."
        ),
        symptom_signals=(
            "deployment_change", "error_rate_increase_post_deploy",
            "latency_increase_post_deploy", "regression_after_release",
        ),
        symptom_keywords=(
            "deployment", "deploy", "release", "rollback", "regression", "post-deploy",
            "deploy correlated", "commit", "version", "newly deployed",
        ),
        common_causes=(
            "code_regression", "config_change", "dependency_version_change",
            "schema_migration_error", "feature_flag_change",
        ),
        plausible_remediations=(
            "rollback_deployment", "revert_config_change", "feature_flag_disable",
            "hotfix_deploy",
        ),
        incompatible_remediations=(
            "add_database_index", "increase_pool_size", "scale_consumers",
            "flush_cache",
        ),
        latent_states=(
            "deployment_regression", "config_drift", "schema_incompatibility",
        ),
    ),
    FailureMechanism(
        mechanism_id="query_fanout_amplification",
        name="Query Fanout Amplification",
        description=(
            "A single application request triggers a disproportionate number of database "
            "queries, overwhelming the database with a query fanout that was not apparent "
            "under lower traffic."
        ),
        symptom_signals=(
            "db_query_count_spike", "db_cpu_high", "n_plus_one_query",
            "query_amplification",
        ),
        symptom_keywords=(
            "query fanout", "n+1", "n plus one", "query amplification", "orm query",
            "excessive queries", "query explosion", "too many queries", "db cpu",
        ),
        common_causes=(
            "orm_lazy_loading", "missing_eager_load", "deployment_regression",
            "traffic_spike_with_inefficient_query",
        ),
        plausible_remediations=(
            "add_eager_loading", "add_database_index", "rollback_deployment",
            "add_query_caching", "optimize_orm_query",
        ),
        incompatible_remediations=(
            "scale_frontend", "flush_cache", "scale_consumers",
            "restart_load_balancer",
        ),
        latent_states=(
            "query_amplification", "orm_inefficiency", "database_saturation",
        ),
    ),
    FailureMechanism(
        mechanism_id="circuit_breaker_instability",
        name="Circuit Breaker Instability",
        description=(
            "A circuit breaker is oscillating between open and half-open states, creating "
            "erratic availability for the protected dependency. Services may see "
            "intermittent failures that do not follow a consistent pattern."
        ),
        symptom_signals=(
            "circuit_breaker_open", "intermittent_failures", "half_open_state",
            "circuit_trip_count",
        ),
        symptom_keywords=(
            "circuit breaker", "circuit open", "circuit tripped", "half open",
            "breaker instability", "circuit flapping", "intermittent",
        ),
        common_causes=(
            "downstream_instability", "threshold_misconfiguration",
            "slow_recovery_of_dependency", "timeout_too_short",
        ),
        plausible_remediations=(
            "tune_circuit_breaker_threshold", "increase_timeout", "fix_downstream_service",
            "add_fallback_behavior",
        ),
        incompatible_remediations=(
            "add_database_index", "scale_database", "flush_cache",
            "scale_consumers",
        ),
        latent_states=(
            "circuit_breaker_open", "dependency_degraded", "partial_availability",
        ),
    ),
    FailureMechanism(
        mechanism_id="traffic_imbalance",
        name="Traffic Imbalance / Hot Shard",
        description=(
            "Traffic is not evenly distributed across service replicas or data shards. "
            "One or more instances receive disproportionate load, causing hotspot "
            "degradation while other instances appear healthy."
        ),
        symptom_signals=(
            "uneven_load_distribution", "hot_instance", "shard_imbalance",
            "replica_load_difference",
        ),
        symptom_keywords=(
            "hot shard", "hotspot", "load imbalance", "uneven distribution",
            "hot instance", "traffic skew", "shard skew", "unbalanced load",
        ),
        common_causes=(
            "poor_sharding_key", "sticky_session_misconfiguration",
            "load_balancer_misconfiguration", "hash_collision",
        ),
        plausible_remediations=(
            "reshard_data", "fix_load_balancer", "scale_specific_shard",
            "change_sharding_strategy",
        ),
        incompatible_remediations=(
            "add_database_index", "increase_pool_size", "flush_cache",
            "rollback_deployment",
        ),
        latent_states=(
            "hot_replica", "shard_saturation", "uneven_load",
        ),
    ),
    FailureMechanism(
        mechanism_id="slow_downstream_propagation",
        name="Slow Downstream Propagation",
        description=(
            "A degraded downstream dependency is holding threads open in the calling "
            "service, causing upstream resource exhaustion through cascading back-pressure "
            "as synchronous calls accumulate."
        ),
        symptom_signals=(
            "downstream_latency", "upstream_thread_wait", "dependency_timeout",
            "cascading_latency",
        ),
        symptom_keywords=(
            "downstream slow", "dependency latency", "upstream waiting", "cascading",
            "dependency timeout", "slow dependency", "upstream timeout",
        ),
        common_causes=(
            "downstream_service_degradation", "network_congestion",
            "downstream_deployment_regression", "dependency_overload",
        ),
        plausible_remediations=(
            "fix_downstream_service", "add_timeout", "enable_circuit_breaker",
            "cache_downstream_response",
        ),
        incompatible_remediations=(
            "add_database_index", "scale_frontend", "flush_cache",
        ),
        latent_states=(
            "thread_saturation", "upstream_resource_exhaustion", "dependency_degraded",
        ),
    ),
    FailureMechanism(
        mechanism_id="memory_pressure",
        name="Memory Pressure / GC Thrashing",
        description=(
            "Available memory is exhausted or nearly so, causing frequent garbage "
            "collection pauses, OOM kills, or swap usage. GC pauses introduce "
            "stop-the-world latency spikes without proportional CPU increase."
        ),
        symptom_signals=(
            "memory_utilization", "gc_pause_time", "oom_kill", "heap_usage",
            "swap_usage",
        ),
        symptom_keywords=(
            "memory", "heap", "oom", "out of memory", "gc pause", "garbage collection",
            "memory pressure", "heap exhaustion", "memory leak", "swap",
        ),
        common_causes=(
            "memory_leak_in_code", "traffic_spike", "deployment_regression",
            "large_in_memory_data_structure",
        ),
        plausible_remediations=(
            "rollback_deployment", "increase_memory_limit", "fix_memory_leak",
            "reduce_heap_usage", "scale_service",
        ),
        incompatible_remediations=(
            "add_database_index", "increase_pool_size", "flush_cache",
        ),
        latent_states=(
            "heap_saturation", "gc_pressure", "near_oom_state",
        ),
    ),
    FailureMechanism(
        mechanism_id="cascading_amplification",
        name="Cascading Failure Amplification",
        description=(
            "A failure in one service causes partial degradation in dependents, which "
            "themselves become overloaded and fail, creating a multi-service cascading "
            "collapse. Error rates and latency grow rapidly across services."
        ),
        symptom_signals=(
            "multi_service_error_spike", "cascading_latency", "service_chain_failure",
            "downstream_error_propagation",
        ),
        symptom_keywords=(
            "cascading", "cascade", "service chain", "multi-service", "spreading failure",
            "domino", "blast radius", "propagating failure",
        ),
        common_causes=(
            "missing_circuit_breaker", "retry_storm", "no_bulkhead_isolation",
            "single_point_of_failure",
        ),
        plausible_remediations=(
            "enable_circuit_breaker", "add_bulkhead", "isolate_failing_service",
            "shed_load", "rollback_deployment",
        ),
        incompatible_remediations=(
            "add_database_index", "flush_cache", "scale_consumers",
        ),
        latent_states=(
            "cascade_propagating", "multi_service_degradation", "blast_radius_growing",
        ),
    ),
    FailureMechanism(
        mechanism_id="noisy_alert_amplification",
        name="Noisy Alert Amplification",
        description=(
            "Alert thresholds are miscalibrated or alert logic is evaluating normal "
            "transient variation. The incident represents false positive noise rather "
            "than real infrastructure degradation."
        ),
        symptom_signals=(
            "alert_without_user_impact", "transient_spike", "self_resolving",
            "brief_threshold_breach",
        ),
        symptom_keywords=(
            "noisy alert", "false positive", "transient", "self-resolving",
            "brief spike", "alert noise", "threshold too tight", "no user impact",
        ),
        common_causes=(
            "miscalibrated_threshold", "missing_alert_dampening",
            "time_window_too_short", "metric_noise",
        ),
        plausible_remediations=(
            "tune_alert_threshold", "add_dampening", "increase_evaluation_window",
            "acknowledge_and_monitor",
        ),
        incompatible_remediations=(
            "rollback_deployment", "add_database_index", "scale_service",
            "flush_cache",
        ),
        latent_states=(
            "false_positive_alert", "transient_noise", "self_resolving_event",
        ),
    ),
    FailureMechanism(
        mechanism_id="dependency_collapse",
        name="Silent Dependency Collapse",
        description=(
            "A critical upstream dependency has silently failed or become unavailable, "
            "causing downstream services to degrade without obvious upstream error "
            "signals. The failure may be masked by circuit breakers or fallbacks."
        ),
        symptom_signals=(
            "upstream_unavailable", "silent_failure", "fallback_activated",
            "dependency_health_check_failing",
        ),
        symptom_keywords=(
            "dependency", "upstream", "silent failure", "fallback", "dependency health",
            "upstream unavailable", "dependency collapsed", "external service",
        ),
        common_causes=(
            "upstream_outage", "network_partition", "upstream_deployment_regression",
            "certificate_expiry",
        ),
        plausible_remediations=(
            "fix_upstream_service", "switch_to_fallback", "notify_upstream_team",
            "increase_circuit_breaker_timeout",
        ),
        incompatible_remediations=(
            "add_database_index", "scale_frontend", "flush_cache",
            "scale_consumers",
        ),
        latent_states=(
            "dependency_degraded", "fallback_active", "upstream_health_unknown",
        ),
    ),
]

_MECHANISM_INDEX: dict[str, FailureMechanism] = {m.mechanism_id: m for m in _MECHANISMS}


class FailureMechanismOntology:
    """
    Registry and lookup for the operational failure mechanism ontology.

    Provides mechanism lookup, symptom scoring, and remediation compatibility
    checks against the full mechanism catalog.
    """

    def all_mechanisms(self) -> list[FailureMechanism]:
        return list(_MECHANISMS)

    def get(self, mechanism_id: str) -> FailureMechanism | None:
        return _MECHANISM_INDEX.get(mechanism_id)

    def score_mechanisms(self, text: str) -> list[tuple[FailureMechanism, int]]:
        """
        Score all mechanisms by keyword match count against text.
        Returns sorted list (highest match first).
        """
        scored = [
            (mechanism, mechanism.matches_keywords(text))
            for mechanism in _MECHANISMS
        ]
        return sorted(scored, key=lambda item: item[1], reverse=True)

    def top_mechanism(self, text: str) -> FailureMechanism | None:
        scored = self.score_mechanisms(text)
        if scored and scored[0][1] > 0:
            return scored[0][0]
        return None

    def validate_remediation(
        self,
        remediation_text: str,
        mechanism_id: str,
    ) -> tuple[bool, str]:
        mechanism = self.get(mechanism_id)
        if mechanism is None:
            return True, ""
        return mechanism.is_remediation_compatible(remediation_text)

    def mechanisms_for_latent_state(self, latent_state: str) -> list[FailureMechanism]:
        return [m for m in _MECHANISMS if latent_state in m.latent_states]

    def to_dict(self) -> dict[str, Any]:
        return {
            "mechanism_count": len(_MECHANISMS),
            "mechanisms": [
                {
                    "mechanism_id": m.mechanism_id,
                    "name": m.name,
                    "description": m.description,
                    "symptom_keywords": list(m.symptom_keywords),
                    "plausible_remediations": list(m.plausible_remediations),
                    "incompatible_remediations": list(m.incompatible_remediations),
                    "latent_states": list(m.latent_states),
                }
                for m in _MECHANISMS
            ],
        }
