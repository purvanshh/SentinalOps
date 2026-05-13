"""
Primary vs secondary failure classification for SentinelOps Phase 43.

Classifies each causal event into one of five types:

  PRIMARY_CAUSE      — originating failure; no upstream cause explains it
  SECONDARY_EFFECT   — propagated symptom of a primary cause
  COLLATERAL_NOISE   — concurrent but unrelated to the causal chain
  OPERATOR_ACTION    — manual remediation or intentional change
  CASCADING_FAILURE  — systemic failure that propagated through multiple hops

Classification algorithm:
  1. Identify candidate primaries: events with no upstream causal predecessors.
  2. Events in blast radius of a primary are SECONDARY_EFFECT.
  3. Events with operator_action node type are OPERATOR_ACTION.
  4. Events at depth >= 2 in the causal chain are CASCADING_FAILURE.
  5. Events with no path to any primary are COLLATERAL_NOISE.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from causality.event_graph import CausalEventGraph, CausalNode, NodeType


class FailureType(str, Enum):
    PRIMARY_CAUSE = "PRIMARY_CAUSE"
    SECONDARY_EFFECT = "SECONDARY_EFFECT"
    COLLATERAL_NOISE = "COLLATERAL_NOISE"
    OPERATOR_ACTION = "OPERATOR_ACTION"
    CASCADING_FAILURE = "CASCADING_FAILURE"


@dataclass
class ClassifiedEvent:
    """A causal graph node with its assigned failure type."""

    node: CausalNode
    failure_type: FailureType
    causal_depth: int
    rationale: str


def _causal_depth(graph: CausalEventGraph, node_id: str) -> int:
    """Return the length of the longest upstream causal chain."""
    ancestors = graph.causal_ancestors(node_id)
    if not ancestors:
        return 0
    max_depth = 0
    for ancestor in ancestors:
        depth = _causal_depth(graph, ancestor.node_id)
        max_depth = max(max_depth, depth + 1)
    return max_depth


def classify_failures(
    graph: CausalEventGraph,
) -> list[ClassifiedEvent]:
    """
    Classify every node in the graph into a FailureType.

    Returns list of ClassifiedEvent in graph insertion order.
    """
    results: list[ClassifiedEvent] = []

    # Pre-compute causal depths (memoize per node_id)
    depth_cache: dict[str, int] = {}

    def get_depth(node_id: str) -> int:
        if node_id not in depth_cache:
            depth_cache[node_id] = _causal_depth(graph, node_id)
        return depth_cache[node_id]

    for node in graph.nodes:
        depth = get_depth(node.node_id)
        predecessors = graph.predecessors(node.node_id)

        successors = graph.successors(node.node_id)

        if node.node_type == NodeType.OPERATOR_ACTION:
            failure_type = FailureType.OPERATOR_ACTION
            rationale = "node is classified as an operator action"

        elif depth == 0 and not predecessors and not successors:
            failure_type = FailureType.COLLATERAL_NOISE
            rationale = "no causal edges — event is isolated from the causal chain"

        elif depth == 0 and not predecessors and successors:
            failure_type = FailureType.PRIMARY_CAUSE
            rationale = "no upstream causal predecessors — originating failure"

        elif depth >= 2:
            failure_type = FailureType.CASCADING_FAILURE
            rationale = f"causal depth {depth} — propagated through multiple service hops"

        elif depth == 1:
            failure_type = FailureType.SECONDARY_EFFECT
            rationale = "direct downstream effect of a primary cause"

        else:
            failure_type = FailureType.COLLATERAL_NOISE
            rationale = "no causal path to or from any other event"

        results.append(
            ClassifiedEvent(
                node=node,
                failure_type=failure_type,
                causal_depth=depth,
                rationale=rationale,
            )
        )

    return results


def filter_by_type(
    classified: list[ClassifiedEvent],
    *,
    failure_type: FailureType,
) -> list[ClassifiedEvent]:
    """Return only events of the specified failure type."""
    return [c for c in classified if c.failure_type == failure_type]


def primary_causes(classified: list[ClassifiedEvent]) -> list[ClassifiedEvent]:
    return filter_by_type(classified, failure_type=FailureType.PRIMARY_CAUSE)


def secondary_effects(classified: list[ClassifiedEvent]) -> list[ClassifiedEvent]:
    return filter_by_type(classified, failure_type=FailureType.SECONDARY_EFFECT)


def collateral_noise(classified: list[ClassifiedEvent]) -> list[ClassifiedEvent]:
    return filter_by_type(classified, failure_type=FailureType.COLLATERAL_NOISE)


def to_classification_dict(classified: list[ClassifiedEvent]) -> dict[str, Any]:
    """Serialize classification results for API/report output."""
    return {
        "primary_causes": [
            {
                "node_id": c.node.node_id,
                "service": c.node.service,
                "description": c.node.description,
                "rationale": c.rationale,
            }
            for c in primary_causes(classified)
        ],
        "secondary_effects": [
            {
                "node_id": c.node.node_id,
                "service": c.node.service,
                "description": c.node.description,
                "causal_depth": c.causal_depth,
            }
            for c in secondary_effects(classified)
        ],
        "collateral_noise": [
            {"node_id": c.node.node_id, "service": c.node.service}
            for c in collateral_noise(classified)
        ],
        "all_classified": [
            {
                "node_id": c.node.node_id,
                "failure_type": c.failure_type.value,
                "causal_depth": c.causal_depth,
                "rationale": c.rationale,
            }
            for c in classified
        ],
    }
