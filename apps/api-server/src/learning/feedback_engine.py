"""
Operator Feedback Engine for SentinelOps Phase 46.

Captures and operationalizes operator signals:
  - approvals (operator confirmed the AI decision)
  - rejections (operator refused the AI decision)
  - overrides (operator chose a different action)
  - rollbacks (operator reversed the executed action)
  - manual edits (operator changed the hypothesis or remediation)
  - escalation decisions (operator elevated to human review)

Each feedback event produces a FeedbackRecord that can be replayed or
aggregated to adjust future confidence, trust scores, and escalation thresholds.

Design constraints:
  - Feedback NEVER silently overrides safeguards.
  - All adaptation is bounded (not unbounded online learning).
  - Every adjustment is logged with a reason.
  - Autonomy does NOT increase from feedback.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class FeedbackKind(str, Enum):
    APPROVAL = "approval"
    REJECTION = "rejection"
    OVERRIDE = "override"
    ROLLBACK = "rollback"
    MANUAL_EDIT = "manual_edit"
    ESCALATION = "escalation"
    FALSE_POSITIVE_CONFIRMATION = "false_positive_confirmation"


@dataclass
class FeedbackRecord:
    """Single operator feedback event with full provenance."""

    incident_id: str
    feedback_kind: FeedbackKind
    mechanism_id: str | None
    remediation_class: str | None
    incident_category: str
    ai_confidence: float
    operator_id: str
    note: str = ""
    ai_recommendation: str = ""
    operator_choice: str = ""
    required_rollback: bool = False
    was_false_positive: bool = False
    timestamp_iso: str = ""

    @property
    def is_correction(self) -> bool:
        return self.feedback_kind in (
            FeedbackKind.REJECTION,
            FeedbackKind.OVERRIDE,
            FeedbackKind.ROLLBACK,
        )

    @property
    def signal_weight(self) -> float:
        """Normalized weight of this feedback for learning. Higher = stronger signal."""
        weights = {
            FeedbackKind.ROLLBACK: 1.0,
            FeedbackKind.REJECTION: 0.8,
            FeedbackKind.OVERRIDE: 0.7,
            FeedbackKind.ESCALATION: 0.5,
            FeedbackKind.MANUAL_EDIT: 0.4,
            FeedbackKind.APPROVAL: 0.1,
            FeedbackKind.FALSE_POSITIVE_CONFIRMATION: 0.6,
        }
        return weights.get(self.feedback_kind, 0.1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "feedback_kind": self.feedback_kind.value,
            "mechanism_id": self.mechanism_id,
            "remediation_class": self.remediation_class,
            "incident_category": self.incident_category,
            "ai_confidence": round(self.ai_confidence, 4),
            "operator_id": self.operator_id,
            "note": self.note,
            "ai_recommendation": self.ai_recommendation,
            "operator_choice": self.operator_choice,
            "required_rollback": self.required_rollback,
            "was_false_positive": self.was_false_positive,
            "is_correction": self.is_correction,
            "signal_weight": self.signal_weight,
            "timestamp_iso": self.timestamp_iso,
        }


@dataclass
class FeedbackSummary:
    """Aggregate statistics over a set of feedback records."""

    total_events: int
    approval_count: int
    rejection_count: int
    override_count: int
    rollback_count: int
    escalation_count: int
    false_positive_count: int
    correction_rate: float
    rollback_rate: float
    weighted_negative_signal: float
    dominant_correction_reason: str
    mechanisms_with_corrections: list[str]
    remediations_with_rollbacks: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_events": self.total_events,
            "approval_count": self.approval_count,
            "rejection_count": self.rejection_count,
            "override_count": self.override_count,
            "rollback_count": self.rollback_count,
            "escalation_count": self.escalation_count,
            "false_positive_count": self.false_positive_count,
            "correction_rate": round(self.correction_rate, 4),
            "rollback_rate": round(self.rollback_rate, 4),
            "weighted_negative_signal": round(self.weighted_negative_signal, 4),
            "dominant_correction_reason": self.dominant_correction_reason,
            "mechanisms_with_corrections": self.mechanisms_with_corrections,
            "remediations_with_rollbacks": self.remediations_with_rollbacks,
        }


class OperatorFeedbackEngine:
    """
    Captures and operationalizes operator feedback signals.

    Maintains an in-process record of feedback events that can be queried
    to understand whether the AI system was operationally correct, not just
    whether the pipeline completed.
    """

    def __init__(self) -> None:
        self._records: list[FeedbackRecord] = []

    def record(self, record: FeedbackRecord) -> None:
        """Add a feedback record."""
        self._records.append(record)

    def record_approval(
        self,
        *,
        incident_id: str,
        mechanism_id: str | None,
        remediation_class: str | None,
        incident_category: str,
        ai_confidence: float,
        operator_id: str,
        note: str = "",
        ai_recommendation: str = "",
        timestamp_iso: str = "",
    ) -> FeedbackRecord:
        rec = FeedbackRecord(
            incident_id=incident_id,
            feedback_kind=FeedbackKind.APPROVAL,
            mechanism_id=mechanism_id,
            remediation_class=remediation_class,
            incident_category=incident_category,
            ai_confidence=ai_confidence,
            operator_id=operator_id,
            note=note,
            ai_recommendation=ai_recommendation,
            timestamp_iso=timestamp_iso,
        )
        self._records.append(rec)
        return rec

    def record_rejection(
        self,
        *,
        incident_id: str,
        mechanism_id: str | None,
        remediation_class: str | None,
        incident_category: str,
        ai_confidence: float,
        operator_id: str,
        note: str = "",
        ai_recommendation: str = "",
        operator_choice: str = "",
        timestamp_iso: str = "",
    ) -> FeedbackRecord:
        rec = FeedbackRecord(
            incident_id=incident_id,
            feedback_kind=FeedbackKind.REJECTION,
            mechanism_id=mechanism_id,
            remediation_class=remediation_class,
            incident_category=incident_category,
            ai_confidence=ai_confidence,
            operator_id=operator_id,
            note=note,
            ai_recommendation=ai_recommendation,
            operator_choice=operator_choice,
            timestamp_iso=timestamp_iso,
        )
        self._records.append(rec)
        return rec

    def record_rollback(
        self,
        *,
        incident_id: str,
        mechanism_id: str | None,
        remediation_class: str | None,
        incident_category: str,
        ai_confidence: float,
        operator_id: str,
        note: str = "",
        timestamp_iso: str = "",
    ) -> FeedbackRecord:
        rec = FeedbackRecord(
            incident_id=incident_id,
            feedback_kind=FeedbackKind.ROLLBACK,
            mechanism_id=mechanism_id,
            remediation_class=remediation_class,
            incident_category=incident_category,
            ai_confidence=ai_confidence,
            operator_id=operator_id,
            note=note,
            required_rollback=True,
            timestamp_iso=timestamp_iso,
        )
        self._records.append(rec)
        return rec

    def record_false_positive(
        self,
        *,
        incident_id: str,
        incident_category: str,
        ai_confidence: float,
        operator_id: str,
        note: str = "",
        timestamp_iso: str = "",
    ) -> FeedbackRecord:
        rec = FeedbackRecord(
            incident_id=incident_id,
            feedback_kind=FeedbackKind.FALSE_POSITIVE_CONFIRMATION,
            mechanism_id=None,
            remediation_class=None,
            incident_category=incident_category,
            ai_confidence=ai_confidence,
            operator_id=operator_id,
            note=note,
            was_false_positive=True,
            timestamp_iso=timestamp_iso,
        )
        self._records.append(rec)
        return rec

    def all_records(self) -> list[FeedbackRecord]:
        return list(self._records)

    def records_for_mechanism(self, mechanism_id: str) -> list[FeedbackRecord]:
        return [r for r in self._records if r.mechanism_id == mechanism_id]

    def records_for_category(self, incident_category: str) -> list[FeedbackRecord]:
        return [r for r in self._records if r.incident_category == incident_category]

    def records_for_remediation(self, remediation_class: str) -> list[FeedbackRecord]:
        return [r for r in self._records if r.remediation_class == remediation_class]

    def summarize(self, records: list[FeedbackRecord] | None = None) -> FeedbackSummary:
        """Compute aggregate statistics over feedback records."""
        target = records if records is not None else self._records
        if not target:
            return FeedbackSummary(
                total_events=0,
                approval_count=0,
                rejection_count=0,
                override_count=0,
                rollback_count=0,
                escalation_count=0,
                false_positive_count=0,
                correction_rate=0.0,
                rollback_rate=0.0,
                weighted_negative_signal=0.0,
                dominant_correction_reason="",
                mechanisms_with_corrections=[],
                remediations_with_rollbacks=[],
            )

        approvals = [r for r in target if r.feedback_kind == FeedbackKind.APPROVAL]
        rejections = [r for r in target if r.feedback_kind == FeedbackKind.REJECTION]
        overrides = [r for r in target if r.feedback_kind == FeedbackKind.OVERRIDE]
        rollbacks = [r for r in target if r.feedback_kind == FeedbackKind.ROLLBACK]
        escalations = [r for r in target if r.feedback_kind == FeedbackKind.ESCALATION]
        false_positives = [
            r for r in target if r.feedback_kind == FeedbackKind.FALSE_POSITIVE_CONFIRMATION
        ]
        corrections = [r for r in target if r.is_correction]

        total = len(target)
        correction_rate = len(corrections) / total if total > 0 else 0.0
        rollback_rate = len(rollbacks) / total if total > 0 else 0.0
        weighted_neg = sum(r.signal_weight for r in corrections) / total if total > 0 else 0.0

        # Dominant correction reason from notes
        notes = [r.note for r in corrections if r.note]
        dominant_reason = notes[0] if notes else "no correction note provided"

        mechs_with_corrections = list(
            {r.mechanism_id for r in corrections if r.mechanism_id}
        )
        rems_with_rollbacks = list(
            {r.remediation_class for r in rollbacks if r.remediation_class}
        )

        return FeedbackSummary(
            total_events=total,
            approval_count=len(approvals),
            rejection_count=len(rejections),
            override_count=len(overrides),
            rollback_count=len(rollbacks),
            escalation_count=len(escalations),
            false_positive_count=len(false_positives),
            correction_rate=round(correction_rate, 4),
            rollback_rate=round(rollback_rate, 4),
            weighted_negative_signal=round(weighted_neg, 4),
            dominant_correction_reason=dominant_reason,
            mechanisms_with_corrections=mechs_with_corrections,
            remediations_with_rollbacks=rems_with_rollbacks,
        )

    def confidence_adjustment_for_mechanism(self, mechanism_id: str) -> float:
        """
        Return a bounded confidence adjustment for a mechanism based on feedback.

        Negative value = reduce confidence for this mechanism.
        Range: [-0.30, 0.05]. Never increases confidence aggressively.
        """
        recs = self.records_for_mechanism(mechanism_id)
        if not recs:
            return 0.0
        summary = self.summarize(recs)
        # Weight: correction_rate drives penalty; approval signals minor positive
        penalty = summary.weighted_negative_signal * 0.40
        boost = (summary.approval_count / len(recs)) * 0.05
        adjustment = boost - penalty
        return round(max(-0.30, min(0.05, adjustment)), 4)
