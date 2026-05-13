"""
Semantic Evidence Normalizer for SentinelOps Phase 45.

Maps lexically distinct evidence descriptions to canonical operational
concepts. This addresses the gap where semantically equivalent signals
are treated as unrelated because they use different surface words.

Examples of semantic equivalence this normalizer captures:
  "DB timeout spike"             → connection_pool_starvation signals
  "connection acquisition wait"  → connection_pool_starvation signals
  "pool exhaustion"              → connection_pool_starvation signals
  "consumer group lag"           → queue_buildup_backpressure signals
  "request amplification"        → retry_storm signals
  "lock wait time"               → lock_contention signals
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class NormalizedConcept:
    canonical_id: str
    canonical_name: str
    operational_meaning: str
    mechanism_hints: list[str]
    severity_weight: float = 1.0


@dataclass
class NormalizationResult:
    original_text: str
    canonical_concept: NormalizedConcept | None
    confidence: float
    raw_matches: list[str]

    @property
    def is_normalized(self) -> bool:
        return self.canonical_concept is not None


_CONCEPT_MAP: list[tuple[list[str], NormalizedConcept]] = [
    (
        [
            "connection pool", "pool exhausted", "db timeout", "connection wait",
            "acquisition latency", "connection limit", "waiting for connection",
            "pool starvation", "db connections", "connection queue",
        ],
        NormalizedConcept(
            canonical_id="db_connection_exhaustion",
            canonical_name="Database Connection Exhaustion",
            operational_meaning=(
                "The database connection pool is at or near capacity. Requests are "
                "queuing for connections rather than being served."
            ),
            mechanism_hints=["connection_pool_starvation", "lock_contention"],
            severity_weight=1.4,
        ),
    ),
    (
        [
            "consumer lag", "kafka lag", "queue depth", "message backlog",
            "consumer behind", "queue buildup", "backpressure", "producer blocked",
        ],
        NormalizedConcept(
            canonical_id="queue_consumer_lag",
            canonical_name="Queue Consumer Lag",
            operational_meaning=(
                "Message consumers are falling behind producers. Queue depth is "
                "growing and processing latency is increasing."
            ),
            mechanism_hints=["queue_buildup_backpressure"],
            severity_weight=1.2,
        ),
    ),
    (
        [
            "retry", "retrying", "retry storm", "request amplification",
            "exponential backoff", "cascading retries", "thundering herd",
        ],
        NormalizedConcept(
            canonical_id="retry_amplification",
            canonical_name="Retry-Driven Request Amplification",
            operational_meaning=(
                "Client or middleware retries are amplifying the request rate against "
                "a degraded service, preventing recovery."
            ),
            mechanism_hints=["retry_storm", "cascading_amplification"],
            severity_weight=1.3,
        ),
    ),
    (
        [
            "lock wait", "deadlock", "lock contention", "serialization failure",
            "row lock", "table lock", "transaction block", "long transaction",
        ],
        NormalizedConcept(
            canonical_id="db_lock_contention",
            canonical_name="Database Lock Contention",
            operational_meaning=(
                "Database row or table locks are blocking concurrent transactions. "
                "Lock holders are preventing progress in other queries."
            ),
            mechanism_hints=["lock_contention"],
            severity_weight=1.3,
        ),
    ),
    (
        [
            "thread pool", "thread exhaustion", "thread starvation", "blocked threads",
            "thread limit", "executor queue", "thread busy",
        ],
        NormalizedConcept(
            canonical_id="thread_pool_saturation",
            canonical_name="Thread Pool Saturation",
            operational_meaning=(
                "The application thread pool is saturated. New requests cannot be "
                "served until existing threads complete or free up."
            ),
            mechanism_hints=["thread_exhaustion", "slow_downstream_propagation"],
            severity_weight=1.2,
        ),
    ),
    (
        [
            "stale cache", "cache poison", "stale data", "cache invalidation",
            "cache inconsistency", "stale entry", "incorrect cached",
        ],
        NormalizedConcept(
            canonical_id="cache_data_staleness",
            canonical_name="Cache Data Staleness",
            operational_meaning=(
                "Cached entries contain stale or incorrect data. High hit rates "
                "mask the staleness from surface-level monitoring."
            ),
            mechanism_hints=["stale_cache_poisoning"],
            severity_weight=1.1,
        ),
    ),
    (
        [
            "n+1", "n plus one", "query fanout", "query amplification",
            "orm query", "excessive queries", "too many queries", "db cpu",
        ],
        NormalizedConcept(
            canonical_id="query_amplification",
            canonical_name="Query Fanout Amplification",
            operational_meaning=(
                "Each application request triggers a disproportionate number of "
                "database queries, overwhelming the database."
            ),
            mechanism_hints=["query_fanout_amplification", "connection_pool_starvation"],
            severity_weight=1.3,
        ),
    ),
    (
        [
            "memory pressure", "heap exhaustion", "gc pause", "oom", "out of memory",
            "garbage collection", "memory leak", "heap usage",
        ],
        NormalizedConcept(
            canonical_id="memory_exhaustion",
            canonical_name="Memory Pressure / GC Thrashing",
            operational_meaning=(
                "Available memory is near exhaustion or GC pauses are introducing "
                "latency spikes without corresponding CPU increase."
            ),
            mechanism_hints=["memory_pressure"],
            severity_weight=1.4,
        ),
    ),
    (
        [
            "circuit breaker", "circuit open", "circuit tripped", "half open",
            "breaker tripped", "circuit flapping",
        ],
        NormalizedConcept(
            canonical_id="circuit_breaker_activation",
            canonical_name="Circuit Breaker Activation",
            operational_meaning=(
                "A circuit breaker has tripped or is unstable, creating intermittent "
                "or complete unavailability for the protected dependency."
            ),
            mechanism_hints=["circuit_breaker_instability", "dependency_collapse"],
            severity_weight=1.2,
        ),
    ),
    (
        [
            "deployment", "deploy", "rollback", "regression", "post-deploy",
            "newly deployed", "commit introduced", "version bump",
        ],
        NormalizedConcept(
            canonical_id="deployment_regression_signal",
            canonical_name="Deployment Regression Signal",
            operational_meaning=(
                "A recent deployment is temporally correlated with the onset of "
                "degradation. The deployment may have introduced a regression."
            ),
            mechanism_hints=["deployment_induced_regression"],
            severity_weight=1.2,
        ),
    ),
    (
        [
            "cascading", "multi-service", "service chain", "spreading failure",
            "blast radius", "propagating failure", "domino",
        ],
        NormalizedConcept(
            canonical_id="cascading_service_failure",
            canonical_name="Cascading Service Failure",
            operational_meaning=(
                "A failure in one service is propagating through the dependency chain, "
                "causing multi-service degradation."
            ),
            mechanism_hints=["cascading_amplification", "slow_downstream_propagation"],
            severity_weight=1.5,
        ),
    ),
]


def _find_matching_concept(text: str) -> tuple[NormalizedConcept | None, list[str]]:
    lower = text.lower()
    best_concept: NormalizedConcept | None = None
    best_match_count = 0
    best_matched_keywords: list[str] = []

    for keywords, concept in _CONCEPT_MAP:
        matched = [kw for kw in keywords if kw in lower]
        if len(matched) > best_match_count:
            best_match_count = len(matched)
            best_concept = concept
            best_matched_keywords = matched

    return best_concept, best_matched_keywords


class SemanticEvidenceNormalizer:
    """
    Maps evidence text into canonical operational concepts.

    Clusters semantically equivalent evidence descriptions under shared
    operational meaning, allowing the reasoning engine to recognize that
    'DB timeout spike', 'connection acquisition latency', and 'pool exhaustion'
    all point to the same underlying mechanism.
    """

    def normalize_text(self, text: str) -> NormalizationResult:
        concept, matched = _find_matching_concept(text)
        confidence = min(1.0, 0.3 * len(matched)) if matched else 0.0
        return NormalizationResult(
            original_text=text,
            canonical_concept=concept,
            confidence=round(confidence, 4),
            raw_matches=matched,
        )

    def normalize_evidence_items(
        self, evidence_items: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Enrich evidence items with semantic concept information.

        Adds 'semantic_concept_id', 'semantic_concept_name', 'operational_meaning',
        and 'mechanism_hints' to each item that can be normalized.
        """
        enriched: list[dict[str, Any]] = []
        for item in evidence_items:
            item_text = " ".join(
                str(v)
                for k, v in item.items()
                if k in ("summary", "metric", "signature", "description", "item_type")
            )
            result = self.normalize_text(item_text)
            enriched_item = dict(item)
            if result.is_normalized and result.canonical_concept is not None:
                enriched_item["semantic_concept_id"] = result.canonical_concept.canonical_id
                enriched_item["semantic_concept_name"] = result.canonical_concept.canonical_name
                enriched_item["operational_meaning"] = result.canonical_concept.operational_meaning
                enriched_item["mechanism_hints"] = result.canonical_concept.mechanism_hints
                enriched_item["semantic_severity_weight"] = (
                    result.canonical_concept.severity_weight
                )
            enriched.append(enriched_item)
        return enriched

    def cluster_by_concept(
        self, evidence_items: list[dict[str, Any]]
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Group evidence items by their canonical semantic concept.

        Items that cannot be normalized fall under the 'unclassified' bucket.
        """
        clusters: dict[str, list[dict[str, Any]]] = {}
        for item in evidence_items:
            item_text = " ".join(
                str(v)
                for k, v in item.items()
                if k in ("summary", "metric", "signature", "description", "item_type")
            )
            result = self.normalize_text(item_text)
            bucket = (
                result.canonical_concept.canonical_id
                if result.is_normalized and result.canonical_concept
                else "unclassified"
            )
            clusters.setdefault(bucket, []).append(item)
        return clusters

    def dominant_mechanism_hints(
        self, evidence_items: list[dict[str, Any]]
    ) -> list[str]:
        """
        Return mechanism IDs suggested by the most common semantic concepts across evidence.
        """
        hint_counts: dict[str, int] = {}
        for item in evidence_items:
            item_text = " ".join(
                str(v)
                for k, v in item.items()
                if k in ("summary", "metric", "signature", "description", "item_type")
            )
            result = self.normalize_text(item_text)
            if result.is_normalized and result.canonical_concept:
                for hint in result.canonical_concept.mechanism_hints:
                    hint_counts[hint] = hint_counts.get(hint, 0) + 1
        return sorted(hint_counts, key=lambda k: hint_counts[k], reverse=True)
