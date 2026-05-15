"""
longitudinal_operator_eval.py — Phase 49 Commit 6

Multi-session (longitudinal) evaluation of operator performance.  Tracks
usefulness scores, trust levels, override rates, and escalation counts
across sessions and detects improvement or degradation trends over time.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class SessionSummary:
    session_id: str
    operator_id: str
    usefulness_score: float
    trust_at_end: float
    incidents_handled: int
    overrides: int
    escalations: int


@dataclass
class LongitudinalTrend:
    operator_id: str
    session_count: int
    mean_usefulness: float
    usefulness_trend: str  # "IMPROVING" | "STABLE" | "DEGRADING"
    mean_trust: float
    trust_trend: str  # "IMPROVING" | "STABLE" | "DEGRADING"
    total_incidents: int
    total_overrides: int
    total_escalations: int


# ---------------------------------------------------------------------------
# Evaluator class
# ---------------------------------------------------------------------------


class LongitudinalOperatorEvaluator:
    """
    Accumulates per-session summaries and computes longitudinal trends
    for individual operators or the full operator population.

    Trend detection
    ---------------
    Sessions are split into a first half and a last half.  The mean of
    the last half minus the mean of the first half determines the trend:
      > +0.05  → IMPROVING
      < -0.05  → DEGRADING
      otherwise → STABLE
    """

    _TREND_THRESHOLD: float = 0.05

    def __init__(self) -> None:
        # operator_id → ordered list of session summaries
        self._sessions: dict[str, list[SessionSummary]] = defaultdict(list)

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add_session(self, summary: SessionSummary) -> None:
        """Append a session summary for the given operator."""
        self._sessions[summary.operator_id].append(summary)

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate_operator(self, operator_id: str) -> LongitudinalTrend:
        """Return a LongitudinalTrend for a single operator."""
        sessions = self._sessions.get(operator_id, [])
        n = len(sessions)

        if n == 0:
            return LongitudinalTrend(
                operator_id=operator_id,
                session_count=0,
                mean_usefulness=0.0,
                usefulness_trend="STABLE",
                mean_trust=0.0,
                trust_trend="STABLE",
                total_incidents=0,
                total_overrides=0,
                total_escalations=0,
            )

        usefulness_scores = [s.usefulness_score for s in sessions]
        trust_scores = [s.trust_at_end for s in sessions]

        mean_usefulness = sum(usefulness_scores) / n
        mean_trust = sum(trust_scores) / n
        total_incidents = sum(s.incidents_handled for s in sessions)
        total_overrides = sum(s.overrides for s in sessions)
        total_escalations = sum(s.escalations for s in sessions)

        usefulness_trend = self._compute_trend(usefulness_scores)
        trust_trend = self._compute_trend(trust_scores)

        return LongitudinalTrend(
            operator_id=operator_id,
            session_count=n,
            mean_usefulness=mean_usefulness,
            usefulness_trend=usefulness_trend,
            mean_trust=mean_trust,
            trust_trend=trust_trend,
            total_incidents=total_incidents,
            total_overrides=total_overrides,
            total_escalations=total_escalations,
        )

    def evaluate_all(self) -> list[LongitudinalTrend]:
        """Evaluate all operators that have at least 2 sessions."""
        return [
            self.evaluate_operator(op_id)
            for op_id, sessions in self._sessions.items()
            if len(sessions) >= 2
        ]

    def top_performers(self, n: int = 3) -> list[LongitudinalTrend]:
        """Return the top-n operators sorted by mean_usefulness descending."""
        all_trends = [self.evaluate_operator(op_id) for op_id in self._sessions]
        return sorted(all_trends, key=lambda t: t.mean_usefulness, reverse=True)[:n]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_trend(self, values: list[float]) -> str:
        """
        Compare the mean of the last half against the mean of the first half.
        With fewer than 2 data points there is no trend to detect → STABLE.
        """
        n = len(values)
        if n < 2:
            return "STABLE"

        mid = n // 2
        first_half = values[:mid]
        last_half = values[mid:]

        mean_first = sum(first_half) / len(first_half)
        mean_last = sum(last_half) / len(last_half)
        delta = mean_last - mean_first

        if delta > self._TREND_THRESHOLD:
            return "IMPROVING"
        if delta < -self._TREND_THRESHOLD:
            return "DEGRADING"
        return "STABLE"
