"""
Operator replay engine for SentinelOps Phase 47.

Replays recorded operator action sequences in chronological order
for counterfactual analysis and operator behavior evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterator

from operators.intervention_tracker import InterventionKind, OperatorIntervention


@dataclass
class ReplayStep:
    """One step in an operator replay session."""

    step_index: int
    intervention: OperatorIntervention
    elapsed_seconds: float  # seconds from first action in this replay
    cumulative_overrides: int
    cumulative_approvals: int


@dataclass
class ReplaySession:
    """Result of replaying a sequence of operator interventions."""

    incident_id: str
    operator_id: str
    total_steps: int
    steps: list[ReplayStep]
    override_count: int
    approval_count: int
    escalation_count: int
    override_rate: float
    has_rollback: bool

    def override_before_step(self, step_index: int) -> int:
        """Count overrides before a given step (exclusive)."""
        return sum(
            1 for s in self.steps if s.step_index < step_index and s.intervention.is_override
        )


class OperatorReplayEngine:
    """
    Replays operator interventions for a single incident or operator.

    Provides chronological iteration, callback registration, and
    session-level statistics for downstream evaluation.
    """

    def __init__(self) -> None:
        self._callbacks: list[Callable[[ReplayStep], None]] = []

    def register_callback(self, fn: Callable[[ReplayStep], None]) -> None:
        self._callbacks.append(fn)

    def replay_incident(
        self,
        incident_id: str,
        interventions: list[OperatorIntervention],
    ) -> ReplaySession:
        """Replay all interventions for a given incident in time order."""
        sorted_ivs = sorted(interventions, key=lambda iv: iv.timestamp_iso)
        steps = self._build_steps(sorted_ivs)

        override_count = sum(1 for s in steps if s.intervention.is_override)
        approval_count = sum(1 for s in steps if s.intervention.is_approval)
        escalation_count = sum(1 for s in steps if s.intervention.is_escalation)
        has_rollback = any(s.intervention.kind == InterventionKind.ROLLBACK for s in steps)
        n = len(steps)
        override_rate = override_count / n if n > 0 else 0.0

        operators = {s.intervention.operator_id for s in steps}
        operator_id = next(iter(operators)) if len(operators) == 1 else "mixed"

        session = ReplaySession(
            incident_id=incident_id,
            operator_id=operator_id,
            total_steps=n,
            steps=steps,
            override_count=override_count,
            approval_count=approval_count,
            escalation_count=escalation_count,
            override_rate=override_rate,
            has_rollback=has_rollback,
        )
        for step in steps:
            for cb in self._callbacks:
                cb(step)
        return session

    def replay_operator(
        self,
        operator_id: str,
        interventions: list[OperatorIntervention],
    ) -> dict[str, ReplaySession]:
        """Replay all interventions for one operator, grouped by incident."""
        by_incident: dict[str, list[OperatorIntervention]] = {}
        for iv in interventions:
            by_incident.setdefault(iv.incident_id, []).append(iv)

        return {iid: self.replay_incident(iid, ivs) for iid, ivs in by_incident.items()}

    def iter_steps(self, interventions: list[OperatorIntervention]) -> Iterator[ReplayStep]:
        """Iterate replay steps without building a full ReplaySession."""
        sorted_ivs = sorted(interventions, key=lambda iv: iv.timestamp_iso)
        yield from self._build_steps(sorted_ivs)

    # ------------------------------------------------------------------

    def _build_steps(self, sorted_ivs: list[OperatorIntervention]) -> list[ReplayStep]:
        steps: list[ReplayStep] = []
        cum_overrides = 0
        cum_approvals = 0
        t0 = sorted_ivs[0].timestamp_iso if sorted_ivs else ""

        for idx, iv in enumerate(sorted_ivs):
            elapsed = self._elapsed_seconds(t0, iv.timestamp_iso)
            if iv.is_override:
                cum_overrides += 1
            if iv.is_approval:
                cum_approvals += 1
            steps.append(
                ReplayStep(
                    step_index=idx,
                    intervention=iv,
                    elapsed_seconds=elapsed,
                    cumulative_overrides=cum_overrides,
                    cumulative_approvals=cum_approvals,
                )
            )
        return steps

    @staticmethod
    def _elapsed_seconds(t0: str, t1: str) -> float:
        if not t0 or not t1:
            return 0.0
        try:
            dt0 = _parse_iso(t0)
            dt1 = _parse_iso(t1)
            return max(0.0, (dt1 - dt0).total_seconds())
        except Exception:
            return 0.0


def _parse_iso(ts: str):
    from datetime import datetime

    ts = ts.replace("Z", "+00:00")
    return datetime.fromisoformat(ts)
