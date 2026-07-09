"""
Operator Feedback Learning System for SentinelOps Phase 11.

Closes the learning loop: instead of a static pipeline that predicts once
and forgets, this system stores operator corrections and uses them to
improve future reasoning.

Flow:
    Incident → Prediction → Operator edits → Store correction → Improve future

Feedback types:
    - accepted: prediction was correct
    - modified: prediction was close but needed correction
    - rejected: prediction was wrong, operator supplied correct root cause

Over time, the system learns organizational patterns like:
    "Deployment regressions are frequently actually configuration regressions"
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class InvestigationFeedback:
    """Stores operator feedback for a single investigation."""

    incident_id: str
    timestamp: float
    prediction: str
    prediction_mechanism: str
    prediction_confidence: float
    operator_root_cause: str = ""
    operator_mechanism: str = ""
    status: str = "pending"  # pending | accepted | modified | rejected
    reason: str = ""
    resolution_time_minutes: float = 0.0
    operator_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def was_correct(self) -> bool:
        return self.status == "accepted"

    @property
    def was_close(self) -> bool:
        return self.status == "modified"

    @property
    def was_wrong(self) -> bool:
        return self.status == "rejected"

    def to_dict(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "timestamp": self.timestamp,
            "prediction": self.prediction,
            "prediction_mechanism": self.prediction_mechanism,
            "prediction_confidence": self.prediction_confidence,
            "operator_root_cause": self.operator_root_cause,
            "operator_mechanism": self.operator_mechanism,
            "status": self.status,
            "reason": self.reason,
            "resolution_time_minutes": self.resolution_time_minutes,
            "operator_id": self.operator_id,
        }


@dataclass
class MechanismCorrection:
    """Learned mapping from predicted mechanism to actual mechanism."""

    predicted: str
    actual: str
    count: int = 0
    confidence_adjustment: float = 0.0


@dataclass
class FeedbackStats:
    """Aggregate statistics over all collected feedback."""

    total_investigations: int = 0
    accepted: int = 0
    modified: int = 0
    rejected: int = 0
    accuracy_rate: float = 0.0
    close_rate: float = 0.0
    mean_resolution_time: float = 0.0
    mechanism_corrections: List[MechanismCorrection] = field(default_factory=list)


class OperatorFeedbackStore:
    """
    Persistent store for operator feedback with learning capabilities.

    Stores feedback entries to a JSON file and computes:
    1. Accuracy statistics over time
    2. Mechanism correction patterns (e.g. deployment_error → config_drift)
    3. Confidence adjustment recommendations
    """

    def __init__(self, storage_path: str | None = None) -> None:
        self._storage_path = Path(storage_path or "/tmp/sentinelops_feedback.json")
        self._feedback: List[InvestigationFeedback] = []
        self._load()

    def _load(self) -> None:
        """Load existing feedback from disk."""
        if self._storage_path.exists():
            try:
                data = json.loads(self._storage_path.read_text())
                for entry in data.get("feedback", []):
                    self._feedback.append(InvestigationFeedback(**entry))
            except Exception:
                self._feedback = []

    def _save(self) -> None:
        """Persist feedback to disk."""
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {"feedback": [f.to_dict() for f in self._feedback]}
        self._storage_path.write_text(json.dumps(data, indent=2))

    def record_feedback(self, feedback: InvestigationFeedback) -> None:
        """Record a new operator feedback entry."""
        self._feedback.append(feedback)
        self._save()

    def accept_prediction(
        self,
        incident_id: str,
        prediction: str,
        mechanism: str,
        confidence: float,
    ) -> InvestigationFeedback:
        """Operator accepts the prediction as correct."""
        fb = InvestigationFeedback(
            incident_id=incident_id,
            timestamp=time.time(),
            prediction=prediction,
            prediction_mechanism=mechanism,
            prediction_confidence=confidence,
            operator_root_cause=prediction,
            operator_mechanism=mechanism,
            status="accepted",
        )
        self.record_feedback(fb)
        return fb

    def modify_prediction(
        self,
        incident_id: str,
        prediction: str,
        mechanism: str,
        confidence: float,
        operator_root_cause: str,
        operator_mechanism: str,
        reason: str = "",
    ) -> InvestigationFeedback:
        """Operator modifies the prediction with a correction."""
        fb = InvestigationFeedback(
            incident_id=incident_id,
            timestamp=time.time(),
            prediction=prediction,
            prediction_mechanism=mechanism,
            prediction_confidence=confidence,
            operator_root_cause=operator_root_cause,
            operator_mechanism=operator_mechanism,
            status="modified",
            reason=reason,
        )
        self.record_feedback(fb)
        return fb

    def reject_prediction(
        self,
        incident_id: str,
        prediction: str,
        mechanism: str,
        confidence: float,
        operator_root_cause: str,
        operator_mechanism: str,
        reason: str = "",
    ) -> InvestigationFeedback:
        """Operator rejects the prediction entirely."""
        fb = InvestigationFeedback(
            incident_id=incident_id,
            timestamp=time.time(),
            prediction=prediction,
            prediction_mechanism=mechanism,
            prediction_confidence=confidence,
            operator_root_cause=operator_root_cause,
            operator_mechanism=operator_mechanism,
            status="rejected",
            reason=reason,
        )
        self.record_feedback(fb)
        return fb

    def compute_stats(self) -> FeedbackStats:
        """Compute aggregate feedback statistics."""
        total = len(self._feedback)
        if total == 0:
            return FeedbackStats()

        accepted = sum(1 for f in self._feedback if f.was_correct)
        modified = sum(1 for f in self._feedback if f.was_close)
        rejected = sum(1 for f in self._feedback if f.was_wrong)

        resolution_times = [
            f.resolution_time_minutes
            for f in self._feedback
            if f.resolution_time_minutes > 0
        ]
        mean_res = sum(resolution_times) / len(resolution_times) if resolution_times else 0

        # Compute mechanism correction patterns
        corrections: Dict[tuple[str, str], int] = {}
        for f in self._feedback:
            if f.status in ("modified", "rejected") and f.operator_mechanism:
                key = (f.prediction_mechanism, f.operator_mechanism)
                corrections[key] = corrections.get(key, 0) + 1

        mechanism_corrections = [
            MechanismCorrection(
                predicted=pred,
                actual=actual,
                count=count,
                confidence_adjustment=-0.1 * count,
            )
            for (pred, actual), count in sorted(corrections.items(), key=lambda x: -x[1])
        ]

        return FeedbackStats(
            total_investigations=total,
            accepted=accepted,
            modified=modified,
            rejected=rejected,
            accuracy_rate=round(accepted / total, 4),
            close_rate=round((accepted + modified) / total, 4),
            mean_resolution_time=round(mean_res, 2),
            mechanism_corrections=mechanism_corrections,
        )

    def get_confidence_adjustment(self, mechanism: str) -> float:
        """
        Get a learned confidence adjustment for a mechanism type.

        If operators frequently correct a mechanism, reduce its confidence.
        If operators frequently accept it, boost slightly.
        """
        relevant = [f for f in self._feedback if f.prediction_mechanism == mechanism]
        if not relevant:
            return 0.0

        accepted = sum(1 for f in relevant if f.was_correct)
        rejected = sum(1 for f in relevant if f.was_wrong)
        total = len(relevant)

        if total < 3:
            return 0.0  # Not enough data to adjust

        accuracy = accepted / total
        if accuracy >= 0.8:
            return 0.05  # Slight boost
        elif accuracy <= 0.3:
            return -0.15  # Significant penalty
        elif accuracy <= 0.5:
            return -0.08  # Moderate penalty

        return 0.0

    def get_mechanism_remapping(self) -> Dict[str, str]:
        """
        Get learned mechanism remappings from feedback.

        E.g. if operators consistently correct 'deployment_error' to
        'configuration_drift', suggest remapping.
        """
        stats = self.compute_stats()
        remappings: Dict[str, str] = {}
        for correction in stats.mechanism_corrections:
            if correction.count >= 3:
                remappings[correction.predicted] = correction.actual
        return remappings

    @property
    def feedback_count(self) -> int:
        return len(self._feedback)
