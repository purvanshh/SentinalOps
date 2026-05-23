"""
Trust Adaptation Engine for SentinelOps Phase 46.

Maintains per-mechanism and per-remediation trust scores that evolve
from operator feedback and execution outcomes.

Trust scores are bounded and decay toward a neutral prior when evidence
is scarce. Adaptation is transparent: every trust update includes a
reason code and the evidence that drove it.

Design constraints:
  - Trust scores are bounded to [0.10, 0.95].
  - Autonomy threshold NEVER increases from trust alone.
  - Trust decay pulls toward 0.50 (neutral) when evidence is stale.
  - All updates produce an auditable TrustUpdateEvent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from learning.feedback_engine import FeedbackKind, FeedbackRecord
from learning.outcome_memory import OutcomeRecord

_TRUST_MIN = 0.10
_TRUST_MAX = 0.95
_TRUST_NEUTRAL = 0.50
_DECAY_RATE = 0.02  # per-staleness step toward neutral
_MIN_SAMPLE_WEIGHT = 5  # below this, updates are dampened


@dataclass
class TrustUpdateEvent:
    """Immutable record of a single trust score change."""

    key: str
    key_type: str  # "mechanism" or "remediation"
    prior_trust: float
    posterior_trust: float
    reason_code: str
    evidence_count: int
    dampened: bool  # True when sample size < _MIN_SAMPLE_WEIGHT
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "key_type": self.key_type,
            "prior_trust": round(self.prior_trust, 4),
            "posterior_trust": round(self.posterior_trust, 4),
            "reason_code": self.reason_code,
            "evidence_count": self.evidence_count,
            "dampened": self.dampened,
            "note": self.note,
        }


@dataclass
class TrustScore:
    """Current trust score for a mechanism or remediation key."""

    key: str
    key_type: str
    score: float
    total_updates: int
    last_reason_code: str
    sample_size_warning: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "key_type": self.key_type,
            "score": round(self.score, 4),
            "total_updates": self.total_updates,
            "last_reason_code": self.last_reason_code,
            "sample_size_warning": self.sample_size_warning,
        }


class TrustAdaptationEngine:
    """
    Adapts mechanism and remediation trust scores from operator feedback
    and execution outcomes.

    Trust scores inform risk scoring and escalation thresholds but never
    directly control autonomy level.
    """

    def __init__(self) -> None:
        self._mechanism_trust: dict[str, float] = {}
        self._remediation_trust: dict[str, float] = {}
        self._mechanism_update_count: dict[str, int] = {}
        self._remediation_update_count: dict[str, int] = {}
        self._history: list[TrustUpdateEvent] = []

    # ------------------------------------------------------------------
    # Read accessors
    # ------------------------------------------------------------------

    def mechanism_trust(self, mechanism_id: str) -> float:
        return self._mechanism_trust.get(mechanism_id, _TRUST_NEUTRAL)

    def remediation_trust(self, remediation_class: str) -> float:
        return self._remediation_trust.get(remediation_class, _TRUST_NEUTRAL)

    def trust_score_for_mechanism(self, mechanism_id: str) -> TrustScore:
        score = self.mechanism_trust(mechanism_id)
        count = self._mechanism_update_count.get(mechanism_id, 0)
        last = self._last_reason("mechanism", mechanism_id)
        return TrustScore(
            key=mechanism_id,
            key_type="mechanism",
            score=score,
            total_updates=count,
            last_reason_code=last,
            sample_size_warning=count < _MIN_SAMPLE_WEIGHT,
        )

    def trust_score_for_remediation(self, remediation_class: str) -> TrustScore:
        score = self.remediation_trust(remediation_class)
        count = self._remediation_update_count.get(remediation_class, 0)
        last = self._last_reason("remediation", remediation_class)
        return TrustScore(
            key=remediation_class,
            key_type="remediation",
            score=score,
            total_updates=count,
            last_reason_code=last,
            sample_size_warning=count < _MIN_SAMPLE_WEIGHT,
        )

    def all_update_events(self) -> list[TrustUpdateEvent]:
        return list(self._history)

    # ------------------------------------------------------------------
    # Feedback-driven updates
    # ------------------------------------------------------------------

    def update_from_feedback(self, record: FeedbackRecord) -> list[TrustUpdateEvent]:
        """Apply a single feedback record to relevant trust scores."""
        events: list[TrustUpdateEvent] = []

        if record.mechanism_id:
            delta = self._feedback_delta(record)
            ev = self._apply_mechanism_delta(
                record.mechanism_id,
                delta,
                reason_code=f"feedback_{record.feedback_kind.value}",
                evidence_count=1,
                note=record.note,
            )
            events.append(ev)

        if record.remediation_class:
            delta = self._feedback_delta(record)
            ev = self._apply_remediation_delta(
                record.remediation_class,
                delta,
                reason_code=f"feedback_{record.feedback_kind.value}",
                evidence_count=1,
                note=record.note,
            )
            events.append(ev)

        return events

    def update_from_outcome(self, record: OutcomeRecord) -> list[TrustUpdateEvent]:
        """Apply an execution outcome record to relevant trust scores."""
        events: list[TrustUpdateEvent] = []

        eff = record.effectiveness_score
        # Convert effectiveness (0–1) to a bounded delta centered on neutral
        # Positive outcomes nudge trust up; harmful outcomes push it down
        if record.was_harmful:
            delta = -0.08
            reason = "outcome_harmful"
        elif eff >= 1.0:
            delta = 0.04
            reason = "outcome_success"
        elif eff >= 0.70:
            delta = 0.02
            reason = "outcome_partial_success"
        elif eff >= 0.50:
            delta = 0.0
            reason = "outcome_neutral"
        else:
            delta = -0.04
            reason = "outcome_failure"

        if record.mechanism_id:
            ev = self._apply_mechanism_delta(
                record.mechanism_id,
                delta,
                reason_code=reason,
                evidence_count=1,
                note=record.execution_note,
            )
            events.append(ev)

        ev = self._apply_remediation_delta(
            record.remediation_class,
            delta,
            reason_code=reason,
            evidence_count=1,
            note=record.execution_note,
        )
        events.append(ev)

        return events

    def apply_feedback_batch(self, records: list[FeedbackRecord]) -> list[TrustUpdateEvent]:
        """Apply a batch of feedback records sequentially."""
        events: list[TrustUpdateEvent] = []
        for rec in records:
            events.extend(self.update_from_feedback(rec))
        return events

    def apply_outcome_batch(self, records: list[OutcomeRecord]) -> list[TrustUpdateEvent]:
        """Apply a batch of outcome records sequentially."""
        events: list[TrustUpdateEvent] = []
        for rec in records:
            events.extend(self.update_from_outcome(rec))
        return events

    # ------------------------------------------------------------------
    # Decay
    # ------------------------------------------------------------------

    def decay_toward_neutral(
        self, mechanism_ids: list[str] | None = None, remediation_classes: list[str] | None = None
    ) -> list[TrustUpdateEvent]:
        """
        Nudge stale trust scores toward neutral (0.50).

        Call this periodically to prevent trust scores from being stuck
        at extremes when fresh evidence hasn't arrived.
        """
        events: list[TrustUpdateEvent] = []
        targets_m = mechanism_ids if mechanism_ids is not None else list(self._mechanism_trust)
        targets_r = (
            remediation_classes
            if remediation_classes is not None
            else list(self._remediation_trust)
        )

        for mid in targets_m:
            current = self._mechanism_trust[mid]
            if abs(current - _TRUST_NEUTRAL) < 0.01:
                continue
            delta = _DECAY_RATE * (1 if current < _TRUST_NEUTRAL else -1)
            ev = self._apply_mechanism_delta(
                mid, delta, reason_code="decay_toward_neutral", evidence_count=0
            )
            events.append(ev)

        for rclass in targets_r:
            current = self._remediation_trust[rclass]
            if abs(current - _TRUST_NEUTRAL) < 0.01:
                continue
            delta = _DECAY_RATE * (1 if current < _TRUST_NEUTRAL else -1)
            ev = self._apply_remediation_delta(
                rclass, delta, reason_code="decay_toward_neutral", evidence_count=0
            )
            events.append(ev)

        return events

    # ------------------------------------------------------------------
    # Querying trust influence on confidence
    # ------------------------------------------------------------------

    def confidence_modifier_for_mechanism(self, mechanism_id: str) -> float:
        """
        Bounded confidence modifier derived from mechanism trust.

        Positive = increase confidence; Negative = decrease confidence.
        Range: [-0.15, 0.10]. Trust must exceed 0.75 for any positive modifier.
        """
        trust = self.mechanism_trust(mechanism_id)
        if trust >= 0.75:
            return round(min(0.10, (trust - 0.75) * 0.40), 4)
        if trust <= 0.30:
            return round(max(-0.15, (trust - 0.30) * 0.50), 4)
        return 0.0

    def remediation_risk_modifier(self, remediation_class: str) -> float:
        """
        Bounded risk modifier derived from remediation trust.

        Negative trust reduces risk tolerance (increases effective risk score).
        Range: [-0.20, 0.0]. Never reduces risk score from trust alone.
        """
        trust = self.remediation_trust(remediation_class)
        if trust <= 0.35:
            return round(max(-0.20, (trust - 0.35) * 0.60), 4)
        return 0.0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _feedback_delta(self, record: FeedbackRecord) -> float:
        kind = record.feedback_kind
        if kind == FeedbackKind.APPROVAL:
            return 0.02
        if kind == FeedbackKind.REJECTION:
            return -0.06
        if kind == FeedbackKind.OVERRIDE:
            return -0.05
        if kind == FeedbackKind.ROLLBACK:
            return -0.10
        if kind == FeedbackKind.ESCALATION:
            return -0.03
        if kind == FeedbackKind.MANUAL_EDIT:
            return -0.02
        if kind == FeedbackKind.FALSE_POSITIVE_CONFIRMATION:
            return -0.04
        return 0.0

    def _apply_mechanism_delta(
        self,
        mechanism_id: str,
        delta: float,
        reason_code: str,
        evidence_count: int,
        note: str = "",
    ) -> TrustUpdateEvent:
        prior = self._mechanism_trust.get(mechanism_id, _TRUST_NEUTRAL)
        count = self._mechanism_update_count.get(mechanism_id, 0)
        dampened = count < _MIN_SAMPLE_WEIGHT
        effective_delta = delta * 0.5 if dampened else delta
        posterior = max(_TRUST_MIN, min(_TRUST_MAX, prior + effective_delta))
        self._mechanism_trust[mechanism_id] = posterior
        self._mechanism_update_count[mechanism_id] = count + 1
        ev = TrustUpdateEvent(
            key=mechanism_id,
            key_type="mechanism",
            prior_trust=round(prior, 4),
            posterior_trust=round(posterior, 4),
            reason_code=reason_code,
            evidence_count=evidence_count,
            dampened=dampened,
            note=note,
        )
        self._history.append(ev)
        return ev

    def _apply_remediation_delta(
        self,
        remediation_class: str,
        delta: float,
        reason_code: str,
        evidence_count: int,
        note: str = "",
    ) -> TrustUpdateEvent:
        prior = self._remediation_trust.get(remediation_class, _TRUST_NEUTRAL)
        count = self._remediation_update_count.get(remediation_class, 0)
        dampened = count < _MIN_SAMPLE_WEIGHT
        effective_delta = delta * 0.5 if dampened else delta
        posterior = max(_TRUST_MIN, min(_TRUST_MAX, prior + effective_delta))
        self._remediation_trust[remediation_class] = posterior
        self._remediation_update_count[remediation_class] = count + 1
        ev = TrustUpdateEvent(
            key=remediation_class,
            key_type="remediation",
            prior_trust=round(prior, 4),
            posterior_trust=round(posterior, 4),
            reason_code=reason_code,
            evidence_count=evidence_count,
            dampened=dampened,
            note=note,
        )
        self._history.append(ev)
        return ev

    def _last_reason(self, key_type: str, key: str) -> str:
        for ev in reversed(self._history):
            if ev.key == key and ev.key_type == key_type:
                return ev.reason_code
        return "no_updates"

    def snapshot(self) -> dict[str, Any]:
        """Return a serializable snapshot of all current trust scores."""
        return {
            "mechanism_trust": {k: round(v, 4) for k, v in self._mechanism_trust.items()},
            "remediation_trust": {k: round(v, 4) for k, v in self._remediation_trust.items()},
            "total_update_events": len(self._history),
        }
