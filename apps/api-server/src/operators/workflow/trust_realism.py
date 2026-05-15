"""
trust_realism.py — Phase 49 Commit 5

Trust realism scoring for AI-to-operator trust dynamics.

CRITICAL INVARIANT: distrust decreases are 2x–3x larger in magnitude
than positive trust increases, reflecting that trust is hard-won but
easily lost in high-stakes operational contexts.

    rollback_loop penalty (0.10) >> positive_outcome gain (0.03)
    false_certainty penalty (0.08)  ≈ 2.7x positive_outcome gain
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

_TRUST_FLOOR: float = 0.05
_TRUST_CEILING: float = 0.90
_INITIAL_TRUST: float = 0.60


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class TrustEvent:
    event_type: str
    trust_delta: float  # positive = trust gained, negative = trust lost
    reason: str
    is_distrust: bool  # True when this event reduces trust


@dataclass
class TrustRealismScore:
    operator_id: str
    current_trust: float  # bounded [0.05, 0.90]
    trust_events: List[TrustEvent]
    trust_earned_from_outcomes: float  # cumulative positive delta
    distrust_from_false_certainty: float  # cumulative negative delta (stored as positive)
    distrust_from_escalation_spam: float  # cumulative negative delta (stored as positive)
    distrust_from_rollbacks: float  # cumulative negative delta (stored as positive)
    distrust_from_vague_recommendations: float  # cumulative negative delta (stored as positive)
    net_trust_change: float  # trust_earned - total_distrust


# ---------------------------------------------------------------------------
# Internal per-operator state
# ---------------------------------------------------------------------------


@dataclass
class _OperatorTrustState:
    current_trust: float = _INITIAL_TRUST
    trust_events: List[TrustEvent] = field(default_factory=list)
    trust_earned_from_outcomes: float = 0.0
    distrust_from_false_certainty: float = 0.0
    distrust_from_escalation_spam: float = 0.0
    distrust_from_rollbacks: float = 0.0
    distrust_from_vague_recommendations: float = 0.0


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


class TrustRealismModel:
    """
    Models trust dynamics between AI recommendations and operator behaviour.

    Trust starts at 0.60 for all operators and evolves through recorded events.
    Distrust penalties are intentionally 2x–3x larger than trust gains.
    """

    def __init__(self) -> None:
        self._states: Dict[str, _OperatorTrustState] = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _state(self, operator_id: str) -> _OperatorTrustState:
        if operator_id not in self._states:
            self._states[operator_id] = _OperatorTrustState()
        return self._states[operator_id]

    def _apply_positive(
        self,
        operator_id: str,
        magnitude: float,
        event_type: str,
        reason: str,
    ) -> TrustEvent:
        state = self._state(operator_id)
        state.current_trust = min(_TRUST_CEILING, state.current_trust + magnitude)
        state.trust_earned_from_outcomes += magnitude
        event = TrustEvent(
            event_type=event_type,
            trust_delta=magnitude,
            reason=reason,
            is_distrust=False,
        )
        state.trust_events.append(event)
        return event

    def _apply_negative(
        self,
        operator_id: str,
        magnitude: float,
        event_type: str,
        reason: str,
        bucket: str,
    ) -> TrustEvent:
        state = self._state(operator_id)
        state.current_trust = max(_TRUST_FLOOR, state.current_trust - magnitude)
        # Accumulate into the correct distrust bucket
        setattr(state, bucket, getattr(state, bucket) + magnitude)
        event = TrustEvent(
            event_type=event_type,
            trust_delta=-magnitude,
            reason=reason,
            is_distrust=True,
        )
        state.trust_events.append(event)
        return event

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_positive_outcome(
        self,
        operator_id: str,
        magnitude: float = 0.03,
    ) -> TrustEvent:
        """A recommendation was accepted and the outcome was successful."""
        return self._apply_positive(
            operator_id,
            magnitude,
            event_type="POSITIVE_OUTCOME",
            reason="Recommendation accepted; outcome verified successful.",
        )

    def record_false_certainty(
        self,
        operator_id: str,
        magnitude: float = 0.08,
    ) -> TrustEvent:
        """AI expressed high confidence but the diagnosis was wrong."""
        return self._apply_negative(
            operator_id,
            magnitude,
            event_type="FALSE_CERTAINTY",
            reason="AI expressed high certainty but diagnosis was incorrect.",
            bucket="distrust_from_false_certainty",
        )

    def record_escalation_spam(
        self,
        operator_id: str,
        magnitude: float = 0.06,
    ) -> TrustEvent:
        """AI generated repeated unnecessary escalations."""
        return self._apply_negative(
            operator_id,
            magnitude,
            event_type="ESCALATION_SPAM",
            reason="Excessive or unnecessary escalations degrading operator trust.",
            bucket="distrust_from_escalation_spam",
        )

    def record_rollback_loop(
        self,
        operator_id: str,
        magnitude: float = 0.10,
    ) -> TrustEvent:
        """A remediation triggered a rollback — highest trust penalty."""
        return self._apply_negative(
            operator_id,
            magnitude,
            event_type="ROLLBACK_LOOP",
            reason="Remediation required rollback; indicates unreliable guidance.",
            bucket="distrust_from_rollbacks",
        )

    def record_vague_recommendation(
        self,
        operator_id: str,
        magnitude: float = 0.05,
    ) -> TrustEvent:
        """AI produced a vague, non-actionable recommendation."""
        return self._apply_negative(
            operator_id,
            magnitude,
            event_type="VAGUE_RECOMMENDATION",
            reason="Recommendation lacked specificity or actionable detail.",
            bucket="distrust_from_vague_recommendations",
        )

    def get_score(self, operator_id: str) -> TrustRealismScore:
        """Return current trust state for the operator."""
        state = self._state(operator_id)
        total_distrust = (
            state.distrust_from_false_certainty
            + state.distrust_from_escalation_spam
            + state.distrust_from_rollbacks
            + state.distrust_from_vague_recommendations
        )
        net_trust_change = state.trust_earned_from_outcomes - total_distrust
        return TrustRealismScore(
            operator_id=operator_id,
            current_trust=state.current_trust,
            trust_events=list(state.trust_events),
            trust_earned_from_outcomes=state.trust_earned_from_outcomes,
            distrust_from_false_certainty=state.distrust_from_false_certainty,
            distrust_from_escalation_spam=state.distrust_from_escalation_spam,
            distrust_from_rollbacks=state.distrust_from_rollbacks,
            distrust_from_vague_recommendations=state.distrust_from_vague_recommendations,
            net_trust_change=net_trust_change,
        )
