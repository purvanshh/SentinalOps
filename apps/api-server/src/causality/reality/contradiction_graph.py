"""
Contradiction graph for Phase 48 causal ambiguity detection.

Tracks pairs of hypotheses that contradict each other:
  - Two hypotheses cannot both be true simultaneously
  - One hypothesis' evidence directly negates another's

The graph is used to detect when the causal picture is fundamentally
irreconcilable — i.e., when no single consistent explanation exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Contradiction:
    cause_a: str
    cause_b: str
    reason: str
    severity: str  # "low" | "medium" | "high"

    def involves(self, mechanism: str) -> bool:
        return mechanism in (self.cause_a, self.cause_b)


@dataclass
class ContradictionGraphReport:
    contradictions: list[Contradiction]
    has_irreconcilable: bool  # True if any high-severity contradiction exists
    most_contradicted: str | None  # mechanism involved in most contradictions

    @property
    def contradiction_count(self) -> int:
        return len(self.contradictions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contradiction_count": self.contradiction_count,
            "has_irreconcilable": self.has_irreconcilable,
            "most_contradicted": self.most_contradicted,
            "contradictions": [
                {
                    "cause_a": c.cause_a,
                    "cause_b": c.cause_b,
                    "reason": c.reason,
                    "severity": c.severity,
                }
                for c in self.contradictions
            ],
        }


class ContradictionGraph:
    """
    Records and analyzes contradictions between causal hypotheses.

    Usage:
        graph = ContradictionGraph()
        graph.add_contradiction("cpu_saturation", "memory_leak",
                                "different resource types; evidence mutually exclusive",
                                severity="high")
        report = graph.analyze()
    """

    def __init__(self) -> None:
        self._contradictions: list[Contradiction] = []

    def add_contradiction(
        self,
        cause_a: str,
        cause_b: str,
        reason: str,
        severity: str = "medium",
    ) -> None:
        self._contradictions.append(Contradiction(cause_a, cause_b, reason, severity))

    def add_from_hypotheses(
        self,
        hypotheses: list[dict[str, Any]],
    ) -> None:
        """
        Auto-detect contradictions from a hypothesis list.

        Heuristic: two hypotheses with similar confidence (gap < 0.05) that
        belong to different causal categories are contradictory.
        """
        cats = {
            "db": ["database", "connection", "pool", "query", "postgres"],
            "network": ["network", "dns", "partition", "timeout", "packet"],
            "memory": ["memory", "heap", "oom", "leak", "gc"],
            "cpu": ["cpu", "throttl", "compute", "load"],
            "deploy": ["deploy", "rollback", "config", "release"],
        }

        def _cat(mechanism: str) -> str:
            m = mechanism.lower()
            for cat, keywords in cats.items():
                if any(k in m for k in keywords):
                    return cat
            return "other"

        sorted_h = sorted(
            hypotheses,
            key=lambda h: float(h.get("confidence", 0.0)),
            reverse=True,
        )
        for i in range(len(sorted_h)):
            for j in range(i + 1, len(sorted_h)):
                conf_a = float(sorted_h[i].get("confidence", 0.0))
                conf_b = float(sorted_h[j].get("confidence", 0.0))
                mech_a = sorted_h[i].get("mechanism", "")
                mech_b = sorted_h[j].get("mechanism", "")
                cat_a = _cat(mech_a)
                cat_b = _cat(mech_b)
                if cat_a != cat_b and abs(conf_a - conf_b) < 0.05:
                    self._contradictions.append(
                        Contradiction(
                            cause_a=mech_a,
                            cause_b=mech_b,
                            reason=(
                                f"different causal categories ({cat_a} vs {cat_b}) "
                                f"with similar confidence ({conf_a:.2f} vs {conf_b:.2f})"
                            ),
                            severity="medium",
                        )
                    )

    def analyze(self) -> ContradictionGraphReport:
        has_irreconcilable = any(c.severity == "high" for c in self._contradictions)

        # Find mechanism involved in most contradictions
        counts: dict[str, int] = {}
        for c in self._contradictions:
            counts[c.cause_a] = counts.get(c.cause_a, 0) + 1
            counts[c.cause_b] = counts.get(c.cause_b, 0) + 1
        most_contradicted = max(counts, key=lambda k: counts[k]) if counts else None

        return ContradictionGraphReport(
            contradictions=list(self._contradictions),
            has_irreconcilable=has_irreconcilable,
            most_contradicted=most_contradicted,
        )

    def clear(self) -> None:
        self._contradictions.clear()
