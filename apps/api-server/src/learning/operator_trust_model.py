"""
Operator Trust Model for SentinelOps Phase 46.

Models per-mechanism and per-remediation trust as seen through the lens
of individual operator behavior patterns. Separate from TrustAdaptationEngine
(which models system-wide trust), this module tracks whether specific
operators consistently agree or disagree with AI assessments on specific
mechanism/remediation combinations.

This data informs:
  - Whether to weight an operator's override more strongly on known topics
  - Whether to surface "frequently challenged by operators" warnings
  - Whether an operator's silence (no feedback) should be treated as
    implicit agreement or disengagement

Design constraints:
  - Models are per-operator, per-mechanism/remediation tuple.
  - No operator is penalized globally — only per-topic agreement rates.
  - Trust is never used to suppress operator ability to override.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from learning.feedback_engine import FeedbackKind, FeedbackRecord


@dataclass
class OperatorMechanismProfile:
    """Operator's agreement pattern for a specific mechanism."""

    operator_id: str
    mechanism_id: str
    total_interactions: int
    agreement_count: int
    correction_count: int
    rollback_count: int
    agreement_rate: float
    most_common_correction_kind: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "operator_id": self.operator_id,
            "mechanism_id": self.mechanism_id,
            "total_interactions": self.total_interactions,
            "agreement_count": self.agreement_count,
            "correction_count": self.correction_count,
            "rollback_count": self.rollback_count,
            "agreement_rate": round(self.agreement_rate, 4),
            "most_common_correction_kind": self.most_common_correction_kind,
        }


@dataclass
class RemediationTrustProfile:
    """System-wide trust profile for a remediation class across all operators."""

    remediation_class: str
    total_interactions: int
    operator_approvals: int
    operator_rejections: int
    operator_rollbacks: int
    consensus_trust_score: float  # 0.0 = all operators rejected, 1.0 = all approved
    controversial: bool  # True if approval_rate is between 0.35 and 0.65

    def to_dict(self) -> dict[str, Any]:
        return {
            "remediation_class": self.remediation_class,
            "total_interactions": self.total_interactions,
            "operator_approvals": self.operator_approvals,
            "operator_rejections": self.operator_rejections,
            "operator_rollbacks": self.operator_rollbacks,
            "consensus_trust_score": round(self.consensus_trust_score, 4),
            "controversial": self.controversial,
        }


class OperatorTrustModel:
    """
    Tracks per-operator, per-mechanism feedback patterns.

    Used to answer: does operator X typically agree with AI on mechanism Y?
    And: is remediation Z controversial among operators?
    """

    def __init__(self) -> None:
        # (operator_id, mechanism_id) → list of FeedbackRecord
        self._operator_mechanism_records: dict[tuple[str, str], list[FeedbackRecord]] = {}
        # (operator_id, remediation_class) → list of FeedbackRecord
        self._operator_remediation_records: dict[tuple[str, str], list[FeedbackRecord]] = {}
        # remediation_class → list of FeedbackRecord
        self._remediation_global_records: dict[str, list[FeedbackRecord]] = {}

    def ingest(self, record: FeedbackRecord) -> None:
        """Ingest a single feedback record into all relevant indexes."""
        if record.mechanism_id:
            key = (record.operator_id, record.mechanism_id)
            self._operator_mechanism_records.setdefault(key, []).append(record)

        if record.remediation_class:
            key_r = (record.operator_id, record.remediation_class)
            self._operator_remediation_records.setdefault(key_r, []).append(record)
            self._remediation_global_records.setdefault(record.remediation_class, []).append(record)

    def ingest_batch(self, records: list[FeedbackRecord]) -> None:
        for rec in records:
            self.ingest(rec)

    def operator_profile_for_mechanism(
        self, operator_id: str, mechanism_id: str
    ) -> OperatorMechanismProfile:
        """Return an operator's agreement pattern for a specific mechanism."""
        key = (operator_id, mechanism_id)
        recs = self._operator_mechanism_records.get(key, [])
        return self._build_operator_mechanism_profile(operator_id, mechanism_id, recs)

    def remediation_consensus(self, remediation_class: str) -> RemediationTrustProfile:
        """Return system-wide consensus trust for a remediation class."""
        recs = self._remediation_global_records.get(remediation_class, [])
        return self._build_remediation_profile(remediation_class, recs)

    def operators_who_challenged_mechanism(self, mechanism_id: str) -> list[str]:
        """Return operator IDs who have issued corrections for a mechanism."""
        result = []
        for (op_id, mech_id), recs in self._operator_mechanism_records.items():
            if mech_id != mechanism_id:
                continue
            if any(r.is_correction for r in recs):
                result.append(op_id)
        return result

    def most_challenged_mechanisms(self, top_n: int = 5) -> list[tuple[str, int]]:
        """Return mechanisms sorted by total correction count descending."""
        counts: dict[str, int] = {}
        for (_, mech_id), recs in self._operator_mechanism_records.items():
            corrections = sum(1 for r in recs if r.is_correction)
            counts[mech_id] = counts.get(mech_id, 0) + corrections
        return sorted(counts.items(), key=lambda x: x[1], reverse=True)[:top_n]

    def most_controversial_remediations(self, top_n: int = 5) -> list[tuple[str, float]]:
        """Return remediations sorted by controversy score (closest to 0.5 approval rate)."""
        results = []
        for rclass, recs in self._remediation_global_records.items():
            profile = self._build_remediation_profile(rclass, recs)
            if profile.total_interactions >= 3:
                controversy = 1.0 - abs(profile.consensus_trust_score - 0.5) * 2
                results.append((rclass, controversy))
        return sorted(results, key=lambda x: x[1], reverse=True)[:top_n]

    def operator_agreement_rate(self, operator_id: str) -> float:
        """
        Overall agreement rate for an operator across all mechanisms.

        Returns 0.5 (neutral) when fewer than 3 interactions exist.
        """
        all_recs: list[FeedbackRecord] = []
        for (op_id, _), recs in self._operator_mechanism_records.items():
            if op_id == operator_id:
                all_recs.extend(recs)
        for (op_id, _), recs in self._operator_remediation_records.items():
            if op_id == operator_id:
                all_recs.extend(recs)
        # Deduplicate by incident_id (one feedback per incident)
        seen: set[str] = set()
        unique: list[FeedbackRecord] = []
        for r in all_recs:
            if r.incident_id not in seen:
                seen.add(r.incident_id)
                unique.append(r)
        if len(unique) < 3:
            return 0.5
        approvals = sum(1 for r in unique if r.feedback_kind == FeedbackKind.APPROVAL)
        return round(approvals / len(unique), 4)

    # ------------------------------------------------------------------
    # Internal builders
    # ------------------------------------------------------------------

    def _build_operator_mechanism_profile(
        self, operator_id: str, mechanism_id: str, recs: list[FeedbackRecord]
    ) -> OperatorMechanismProfile:
        if not recs:
            return OperatorMechanismProfile(
                operator_id=operator_id,
                mechanism_id=mechanism_id,
                total_interactions=0,
                agreement_count=0,
                correction_count=0,
                rollback_count=0,
                agreement_rate=0.5,
                most_common_correction_kind="none",
            )
        agreements = [r for r in recs if r.feedback_kind == FeedbackKind.APPROVAL]
        corrections = [r for r in recs if r.is_correction]
        rollbacks = [r for r in recs if r.feedback_kind == FeedbackKind.ROLLBACK]

        # Most common correction kind
        correction_kinds: dict[str, int] = {}
        for r in corrections:
            correction_kinds[r.feedback_kind.value] = (
                correction_kinds.get(r.feedback_kind.value, 0) + 1
            )
        most_common = (
            max(correction_kinds, key=lambda k: correction_kinds[k]) if correction_kinds else "none"
        )  # noqa: E501

        return OperatorMechanismProfile(
            operator_id=operator_id,
            mechanism_id=mechanism_id,
            total_interactions=len(recs),
            agreement_count=len(agreements),
            correction_count=len(corrections),
            rollback_count=len(rollbacks),
            agreement_rate=round(len(agreements) / len(recs), 4),
            most_common_correction_kind=most_common,
        )

    def _build_remediation_profile(
        self, remediation_class: str, recs: list[FeedbackRecord]
    ) -> RemediationTrustProfile:
        if not recs:
            return RemediationTrustProfile(
                remediation_class=remediation_class,
                total_interactions=0,
                operator_approvals=0,
                operator_rejections=0,
                operator_rollbacks=0,
                consensus_trust_score=0.5,
                controversial=False,
            )
        approvals = sum(1 for r in recs if r.feedback_kind == FeedbackKind.APPROVAL)
        rejections = sum(1 for r in recs if r.feedback_kind == FeedbackKind.REJECTION)
        rollbacks = sum(1 for r in recs if r.feedback_kind == FeedbackKind.ROLLBACK)
        n = len(recs)
        consensus = approvals / n
        controversial = 0.35 <= consensus <= 0.65

        return RemediationTrustProfile(
            remediation_class=remediation_class,
            total_interactions=n,
            operator_approvals=approvals,
            operator_rejections=rejections,
            operator_rollbacks=rollbacks,
            consensus_trust_score=round(consensus, 4),
            controversial=controversial,
        )
