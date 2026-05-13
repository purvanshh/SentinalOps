"""
Temporal causality engine for SentinelOps Phase 43.

Reasons over event ordering to distinguish:
  - originating failures (first in time, upstream in topology)
  - propagated symptoms (came after, downstream)
  - collateral noise (concurrent but unrelated)
  - remediation actions (after peak, intentional)

Key concepts:
  - Propagation window: time lag within which effects are expected to appear
    after a cause. Defaults to 300 seconds (5 minutes) for service hops.
  - Temporal ordering: strict ISO-8601 comparison with timezone awareness.
  - Temporal contradiction: an event cannot cause something that preceded it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from causality.event_graph import CausalEdge, CausalEventGraph, EdgeType

_DEFAULT_PROPAGATION_WINDOW_SECONDS = 300
_DEPLOYMENT_LAG_SECONDS = 120


def _parse_ts(ts: str) -> datetime:
    """Parse ISO-8601 timestamp, always returning UTC-aware datetime."""
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _elapsed_seconds(earlier: str, later: str) -> float:
    """Return seconds between two ISO timestamps. Negative if later < earlier."""
    try:
        return (_parse_ts(later) - _parse_ts(earlier)).total_seconds()
    except (ValueError, TypeError):
        return 0.0


@dataclass
class TemporalOrderViolation:
    """A detected contradiction in event ordering."""

    source_id: str
    target_id: str
    reason: str
    elapsed_seconds: float


def build_temporal_edges(
    graph: CausalEventGraph,
    *,
    propagation_window_seconds: float = _DEFAULT_PROPAGATION_WINDOW_SECONDS,
) -> list[CausalEdge]:
    """
    Inspect all node pairs and add TEMPORAL_PRECEDES edges where:
      - source.timestamp < target.timestamp
      - elapsed time is within propagation_window_seconds

    Returns the list of added edges (also mutates graph).
    """
    nodes = graph.nodes
    added: list[CausalEdge] = []
    for i, source in enumerate(nodes):
        for target in nodes[i + 1 :]:
            if source.node_id == target.node_id:
                continue
            elapsed = _elapsed_seconds(source.timestamp_iso, target.timestamp_iso)
            if 0 < elapsed <= propagation_window_seconds:
                edge = CausalEdge(
                    source_id=source.node_id,
                    target_id=target.node_id,
                    edge_type=EdgeType.TEMPORAL_PRECEDES,
                    weight=1.0 - (elapsed / propagation_window_seconds),
                    rationale=f"source preceded target by {elapsed:.0f}s",
                )
                graph.add_edge(edge)
                added.append(edge)
            elif elapsed < 0 and abs(elapsed) <= propagation_window_seconds:
                edge = CausalEdge(
                    source_id=target.node_id,
                    target_id=source.node_id,
                    edge_type=EdgeType.TEMPORAL_PRECEDES,
                    weight=1.0 - (abs(elapsed) / propagation_window_seconds),
                    rationale=f"target preceded source by {abs(elapsed):.0f}s",
                )
                graph.add_edge(edge)
                added.append(edge)
    return added


def detect_temporal_contradictions(
    events: list[dict[str, Any]],
) -> list[TemporalOrderViolation]:
    """
    Detect events that claim to precede something that already happened.

    An event with claimed_cause earlier than its own timestamp is contradictory.
    Specifically, checks for deployments that occurred AFTER the anomaly started.
    """
    violations: list[TemporalOrderViolation] = []
    anomalies = [e for e in events if e.get("event_type") == "anomaly"]
    deployments = [e for e in events if e.get("event_type") == "deployment"]

    for deploy in deployments:
        for anomaly in anomalies:
            try:
                deploy_ts = deploy.get("timestamp_iso", "")
                anomaly_ts = anomaly.get("timestamp_iso", "")
                if not deploy_ts or not anomaly_ts:
                    continue
                elapsed = _elapsed_seconds(anomaly_ts, deploy_ts)
                if elapsed > 0:
                    violations.append(
                        TemporalOrderViolation(
                            source_id=deploy.get("event_id", "deployment"),
                            target_id=anomaly.get("event_id", "anomaly"),
                            reason=(
                                f"deployment at {deploy_ts} occurred {elapsed:.0f}s "
                                f"AFTER anomaly at {anomaly_ts} — cannot be root cause"
                            ),
                            elapsed_seconds=elapsed,
                        )
                    )
            except (ValueError, TypeError):
                continue
    return violations


def sequence_events_by_time(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort events by timestamp_iso ascending. Events without timestamp sort last."""

    def sort_key(e: dict[str, Any]) -> datetime:
        ts = e.get("timestamp_iso", "")
        try:
            return _parse_ts(ts)
        except (ValueError, TypeError):
            return datetime.max.replace(tzinfo=timezone.utc)

    return sorted(events, key=sort_key)


def compute_propagation_lag(
    cause_timestamp: str,
    effect_timestamp: str,
) -> float:
    """Return seconds between cause and effect. Zero if effect preceded cause."""
    elapsed = _elapsed_seconds(cause_timestamp, effect_timestamp)
    return max(elapsed, 0.0)
