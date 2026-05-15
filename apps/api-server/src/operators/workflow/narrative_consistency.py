"""
Narrative Consistency Checker for SentinelOps Phase 49.

Validates that a sequence of AI-generated incident narratives remains
internally consistent over time as new information arrives:

  - Temporal coherence  — update timestamps are monotonically increasing
  - Confidence drift    — confidence scores don't swing by more than 0.40
  - Contradiction check — later narratives don't contradict earlier ones
    using known antonym pairs

NarrativeConsistencyChecker.check() returns a NarrativeConsistencyReport
which operators and the audit trail can use to surface instability.

Design constraints:
  - Checker is purely advisory — it never blocks execution.
  - `is_consistent` is False only when at least one "high" severity violation
    is present.
  - Timestamps must be ISO-8601 strings (e.g. "2026-05-15T14:30:00Z").
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Antonym pairs used for cross-narrative contradiction detection
# ---------------------------------------------------------------------------
_ANTONYM_PAIRS: list[tuple[str, str]] = [
    ("resolved", "unresolved"),
    ("stable", "degrading"),
    ("healthy", "unhealthy"),
    ("improving", "worsening"),
]

# Threshold above which a confidence swing across the sequence is flagged.
_CONFIDENCE_DRIFT_THRESHOLD: float = 0.40


@dataclass
class ConsistencyViolation:
    """A single consistency violation detected across a narrative sequence."""

    violation_type: str  # e.g. "TEMPORAL_ORDER", "CONFIDENCE_DRIFT", "CONTRADICTION"
    description: str
    severity: str  # "low" | "medium" | "high"


@dataclass
class NarrativeConsistencyReport:
    """Aggregated consistency report for one incident's narrative sequence."""

    incident_id: str
    violations: list[ConsistencyViolation]
    temporal_coherence_score: float  # 1.0 = all in order; -0.2 per inversion
    is_consistent: bool  # False if any "high" violation present
    confidence_drift_detected: bool


class NarrativeConsistencyChecker:
    """
    Checks a sequence of incident narratives for temporal and semantic consistency.

    Usage::

        checker = NarrativeConsistencyChecker()
        report = checker.check(
            incident_id="inc-001",
            narratives=["Service is stable.", "Service is now degrading."],
            confidences=[0.80, 0.45],
            timestamps_iso=["2026-05-15T10:00:00Z", "2026-05-15T10:05:00Z"],
        )
    """

    def check(
        self,
        incident_id: str,
        narratives: list[str],
        confidences: list[float],
        timestamps_iso: list[str],
    ) -> NarrativeConsistencyReport:
        """
        Evaluate consistency across a narrative sequence.

        Parameters
        ----------
        incident_id:
            Unique identifier for the incident being checked.
        narratives:
            Ordered list of narrative text strings (earliest first).
        confidences:
            Confidence score corresponding to each narrative (0.0–1.0).
        timestamps_iso:
            ISO-8601 timestamp string for each narrative entry.

        All three lists must have the same length.  Empty sequences yield a
        fully consistent report with a temporal coherence score of 1.0.
        """
        violations: list[ConsistencyViolation] = []

        if not narratives:
            return NarrativeConsistencyReport(
                incident_id=incident_id,
                violations=[],
                temporal_coherence_score=1.0,
                is_consistent=True,
                confidence_drift_detected=False,
            )

        # ---- 1. Parse timestamps ----------------------------------------
        parsed_timestamps = self._parse_timestamps(timestamps_iso)

        # ---- 2. Temporal coherence --------------------------------------
        temporal_coherence_score, temporal_violations = self._check_temporal_order(
            parsed_timestamps
        )
        violations.extend(temporal_violations)

        # ---- 3. Confidence drift ----------------------------------------
        drift_detected, drift_violations = self._check_confidence_drift(confidences)
        violations.extend(drift_violations)

        # ---- 4. Cross-narrative contradictions --------------------------
        contradiction_violations = self._check_contradictions(narratives)
        violations.extend(contradiction_violations)

        # ---- Outcome ----
        is_consistent = not any(v.severity == "high" for v in violations)

        return NarrativeConsistencyReport(
            incident_id=incident_id,
            violations=violations,
            temporal_coherence_score=round(temporal_coherence_score, 4),
            is_consistent=is_consistent,
            confidence_drift_detected=drift_detected,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_timestamps(timestamps_iso: list[str]) -> list[datetime]:
        """
        Parse ISO-8601 timestamp strings into timezone-aware datetime objects.

        Strings that cannot be parsed are replaced with the Unix epoch so that
        the ordering logic can still proceed (they will be flagged as violations
        by the out-of-order check).
        """
        parsed: list[datetime] = []
        for ts in timestamps_iso:
            try:
                # Python 3.11+ accepts 'Z'; for earlier versions normalise it.
                normalised = ts.replace("Z", "+00:00")
                parsed.append(datetime.fromisoformat(normalised))
            except (ValueError, AttributeError):
                # Fallback: epoch — will almost certainly be flagged as OOO.
                parsed.append(datetime(1970, 1, 1, tzinfo=timezone.utc))
        return parsed

    @staticmethod
    def _check_temporal_order(
        timestamps: list[datetime],
    ) -> tuple[float, list[ConsistencyViolation]]:
        """
        Verify timestamps are strictly non-decreasing.

        Score starts at 1.0 and loses 0.2 per out-of-order adjacent pair.
        Score is clamped to [0.0, 1.0].
        """
        violations: list[ConsistencyViolation] = []
        score = 1.0

        for i in range(1, len(timestamps)):
            if timestamps[i] < timestamps[i - 1]:
                score -= 0.2
                violations.append(
                    ConsistencyViolation(
                        violation_type="TEMPORAL_ORDER",
                        description=(
                            f"Narrative at position {i} has timestamp "
                            f"{timestamps[i].isoformat()} which precedes "
                            f"position {i - 1} timestamp "
                            f"{timestamps[i - 1].isoformat()}."
                        ),
                        severity="high",
                    )
                )

        score = max(0.0, score)
        return score, violations

    @staticmethod
    def _check_confidence_drift(
        confidences: list[float],
    ) -> tuple[bool, list[ConsistencyViolation]]:
        """
        Flag if the confidence range across the sequence exceeds the threshold.
        """
        if len(confidences) < 2:
            return False, []

        drift = max(confidences) - min(confidences)
        if drift > _CONFIDENCE_DRIFT_THRESHOLD:
            return True, [
                ConsistencyViolation(
                    violation_type="CONFIDENCE_DRIFT",
                    description=(
                        f"Confidence swing of {drift:.2f} detected across the "
                        f"narrative sequence (max={max(confidences):.2f}, "
                        f"min={min(confidences):.2f}). "
                        f"Threshold is {_CONFIDENCE_DRIFT_THRESHOLD}."
                    ),
                    severity="medium",
                )
            ]
        return False, []

    @staticmethod
    def _check_contradictions(
        narratives: list[str],
    ) -> list[ConsistencyViolation]:
        """
        Detect semantic contradictions across the narrative sequence.

        For each antonym pair (A, B): if an earlier narrative contains A and a
        later narrative contains B (or vice-versa), a violation is raised.
        """
        violations: list[ConsistencyViolation] = []
        lowered = [n.lower() for n in narratives]

        for term_a, term_b in _ANTONYM_PAIRS:
            for i in range(len(lowered)):
                for j in range(i + 1, len(lowered)):
                    earlier, later = lowered[i], lowered[j]
                    # Earlier says A, later says B.
                    if term_a in earlier and term_b in later:
                        violations.append(
                            ConsistencyViolation(
                                violation_type="CONTRADICTION",
                                description=(
                                    f"Narrative {i} describes '{term_a}' but "
                                    f"narrative {j} describes '{term_b}', "
                                    "which is contradictory."
                                ),
                                severity="high",
                            )
                        )
                    # Earlier says B, later says A.
                    elif term_b in earlier and term_a in later:
                        violations.append(
                            ConsistencyViolation(
                                violation_type="CONTRADICTION",
                                description=(
                                    f"Narrative {i} describes '{term_b}' but "
                                    f"narrative {j} describes '{term_a}', "
                                    "which is contradictory."
                                ),
                                severity="high",
                            )
                        )

        return violations
