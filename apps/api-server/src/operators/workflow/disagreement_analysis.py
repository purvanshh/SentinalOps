"""
disagreement_analysis.py — Phase 49 Commit 5

Analyzes operator disagreements with AI recommendations to surface
patterns such as chronic overriding, rejection clusters, and silent
bypasses that indicate alignment risk.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class DisagreementKind(Enum):
    OVERRIDE = "OVERRIDE"
    REJECTION = "REJECTION"
    DELAYED_ACTION = "DELAYED_ACTION"
    SILENT_BYPASS = "SILENT_BYPASS"
    ESCALATION_SKIP = "ESCALATION_SKIP"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class DisagreementRecord:
    operator_id: str
    incident_id: str
    kind: DisagreementKind
    recommendation_summary: str
    operator_action: str
    rationale: str
    has_justification: bool


@dataclass
class DisagreementPattern:
    pattern_name: str
    frequency: int
    affected_operator_ids: List[str]
    risk_level: str  # "LOW", "MEDIUM", "HIGH"


@dataclass
class DisagreementAnalysisReport:
    total_disagreements: int
    by_kind: Dict[str, int]
    patterns: List[DisagreementPattern]
    unjustified_override_count: int
    systematic_rejection_detected: bool  # REJECTION > 30 % of total
    silent_bypass_detected: bool  # any SILENT_BYPASS present


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------


class DisagreementAnalyzer:
    """
    Records individual operator disagreement events and analyzes them to
    identify systemic patterns and high-risk operator behaviours.
    """

    def __init__(self) -> None:
        self._records: List[DisagreementRecord] = []

    # ------------------------------------------------------------------

    def record(self, record: DisagreementRecord) -> None:
        """Append a disagreement record to the internal store."""
        self._records.append(record)

    # ------------------------------------------------------------------

    def analyze(self) -> DisagreementAnalysisReport:
        """Analyze all recorded disagreements and return a structured report."""
        records = self._records
        total = len(records)

        # Counts by kind
        by_kind: Dict[str, int] = {k.value: 0 for k in DisagreementKind}
        for r in records:
            by_kind[r.kind.value] += 1

        # Unjustified overrides
        unjustified_override_count = sum(
            1 for r in records if r.kind == DisagreementKind.OVERRIDE and not r.has_justification
        )

        # Flags
        rejection_count = by_kind[DisagreementKind.REJECTION.value]
        systematic_rejection_detected = total > 0 and (rejection_count / total) > 0.30
        silent_bypass_detected = by_kind[DisagreementKind.SILENT_BYPASS.value] > 0

        # Pattern detection
        patterns: List[DisagreementPattern] = []
        patterns.extend(self._detect_chronic_override(records, total))
        patterns.extend(self._detect_rejection_cluster(by_kind, total))
        patterns.extend(self._detect_silent_bypass_risk(records, by_kind))

        return DisagreementAnalysisReport(
            total_disagreements=total,
            by_kind=by_kind,
            patterns=patterns,
            unjustified_override_count=unjustified_override_count,
            systematic_rejection_detected=systematic_rejection_detected,
            silent_bypass_detected=silent_bypass_detected,
        )

    # ------------------------------------------------------------------
    # Pattern detectors
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_chronic_override(
        records: List[DisagreementRecord],
        total: int,
    ) -> List[DisagreementPattern]:
        """CHRONIC_OVERRIDE: a single operator has >3 OVERRIDE records."""
        override_counts: Counter[str] = Counter(
            r.operator_id for r in records if r.kind == DisagreementKind.OVERRIDE
        )
        chronic_operators = [op for op, count in override_counts.items() if count > 3]
        if not chronic_operators:
            return []
        frequency = sum(override_counts[op] for op in chronic_operators)
        return [
            DisagreementPattern(
                pattern_name="CHRONIC_OVERRIDE",
                frequency=frequency,
                affected_operator_ids=chronic_operators,
                risk_level="HIGH",
            )
        ]

    @staticmethod
    def _detect_rejection_cluster(
        by_kind: Dict[str, int],
        total: int,
    ) -> List[DisagreementPattern]:
        """REJECTION_CLUSTER: total rejections > 30% of all disagreements."""
        rejection_count = by_kind.get(DisagreementKind.REJECTION.value, 0)
        if total == 0 or (rejection_count / total) <= 0.30:
            return []
        return [
            DisagreementPattern(
                pattern_name="REJECTION_CLUSTER",
                frequency=rejection_count,
                affected_operator_ids=[],
                risk_level="MEDIUM",
            )
        ]

    @staticmethod
    def _detect_silent_bypass_risk(
        records: List[DisagreementRecord],
        by_kind: Dict[str, int],
    ) -> List[DisagreementPattern]:
        """SILENT_BYPASS_RISK: any SILENT_BYPASS events exist."""
        bypass_count = by_kind.get(DisagreementKind.SILENT_BYPASS.value, 0)
        if bypass_count == 0:
            return []
        affected = list(
            {r.operator_id for r in records if r.kind == DisagreementKind.SILENT_BYPASS}
        )
        return [
            DisagreementPattern(
                pattern_name="SILENT_BYPASS_RISK",
                frequency=bypass_count,
                affected_operator_ids=affected,
                risk_level="HIGH",
            )
        ]
