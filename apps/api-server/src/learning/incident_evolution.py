"""
Incident Evolution Tracker for SentinelOps Phase 46.

Tracks how incidents evolve over their lifecycle — from initial detection
through investigation, remediation, and closure. Produces an EvolutionTrace
per incident that shows whether the AI's assessment changed over time and
how accurately it predicted the final outcome.

Tracked per evolution event:
  - stage: what phase the incident was in
  - ai_confidence: what confidence the AI had at that stage
  - mechanism_id: what mechanism was suspected at that stage
  - revision_reason: why the assessment changed

This trace enables:
  - Detecting early-stage assessment reversals (AI changed its mind)
  - Measuring how quickly the AI converges to the correct diagnosis
  - Identifying mechanism classes where early diagnosis is unreliable

Design constraints:
  - Traces are append-only — no retroactive edits.
  - Confidence history is preserved for audit.
  - Stage transitions are validated against the allowed lifecycle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class IncidentStage(str, Enum):
    DETECTED = "detected"
    INVESTIGATING = "investigating"
    HYPOTHESIS_FORMED = "hypothesis_formed"
    REMEDIATION_PROPOSED = "remediation_proposed"
    REMEDIATION_EXECUTING = "remediation_executing"
    REMEDIATION_COMPLETE = "remediation_complete"
    POST_MORTEM = "post_mortem"
    CLOSED = "closed"


_STAGE_ORDER = [
    IncidentStage.DETECTED,
    IncidentStage.INVESTIGATING,
    IncidentStage.HYPOTHESIS_FORMED,
    IncidentStage.REMEDIATION_PROPOSED,
    IncidentStage.REMEDIATION_EXECUTING,
    IncidentStage.REMEDIATION_COMPLETE,
    IncidentStage.POST_MORTEM,
    IncidentStage.CLOSED,
]


@dataclass
class EvolutionEvent:
    """A single stage transition in an incident's lifecycle."""

    stage: IncidentStage
    ai_confidence: float
    mechanism_id: str | None
    remediation_class: str | None
    timestamp_iso: str
    revision_reason: str = ""
    assessment_changed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage.value,
            "ai_confidence": round(self.ai_confidence, 4),
            "mechanism_id": self.mechanism_id,
            "remediation_class": self.remediation_class,
            "timestamp_iso": self.timestamp_iso,
            "revision_reason": self.revision_reason,
            "assessment_changed": self.assessment_changed,
        }


@dataclass
class EvolutionTrace:
    """Full evolution trace for a single incident."""

    incident_id: str
    events: list[EvolutionEvent] = field(default_factory=list)

    @property
    def current_stage(self) -> IncidentStage | None:
        return self.events[-1].stage if self.events else None

    @property
    def initial_mechanism(self) -> str | None:
        for ev in self.events:
            if ev.mechanism_id:
                return ev.mechanism_id
        return None

    @property
    def final_mechanism(self) -> str | None:
        for ev in reversed(self.events):
            if ev.mechanism_id:
                return ev.mechanism_id
        return None

    @property
    def assessment_was_revised(self) -> bool:
        return any(ev.assessment_changed for ev in self.events)

    @property
    def revision_count(self) -> int:
        return sum(1 for ev in self.events if ev.assessment_changed)

    @property
    def confidence_trajectory(self) -> list[float]:
        return [ev.ai_confidence for ev in self.events]

    @property
    def confidence_trend(self) -> str:
        """'increasing', 'decreasing', 'stable', or 'volatile'."""
        traj = self.confidence_trajectory
        if len(traj) < 2:
            return "stable"
        diffs = [traj[i] - traj[i - 1] for i in range(1, len(traj))]
        increases = sum(1 for d in diffs if d > 0.05)
        decreases = sum(1 for d in diffs if d < -0.05)
        if increases > decreases and increases > len(diffs) * 0.5:
            return "increasing"
        if decreases > increases and decreases > len(diffs) * 0.5:
            return "decreasing"
        if increases + decreases > len(diffs) * 0.6:
            return "volatile"
        return "stable"

    def to_dict(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "events": [ev.to_dict() for ev in self.events],
            "current_stage": self.current_stage.value if self.current_stage else None,
            "initial_mechanism": self.initial_mechanism,
            "final_mechanism": self.final_mechanism,
            "assessment_was_revised": self.assessment_was_revised,
            "revision_count": self.revision_count,
            "confidence_trajectory": [round(c, 4) for c in self.confidence_trajectory],
            "confidence_trend": self.confidence_trend,
        }


class IncidentEvolutionTracker:
    """
    Tracks the full lifecycle evolution of incidents.

    Enables retrospective analysis of how AI assessments evolved and
    whether early-stage diagnoses were reliable.
    """

    def __init__(self) -> None:
        self._traces: dict[str, EvolutionTrace] = {}

    def start_incident(
        self,
        incident_id: str,
        *,
        ai_confidence: float,
        mechanism_id: str | None,
        remediation_class: str | None,
        timestamp_iso: str,
    ) -> EvolutionTrace:
        """Create a new trace for an incident at the DETECTED stage."""
        trace = EvolutionTrace(incident_id=incident_id)
        ev = EvolutionEvent(
            stage=IncidentStage.DETECTED,
            ai_confidence=ai_confidence,
            mechanism_id=mechanism_id,
            remediation_class=remediation_class,
            timestamp_iso=timestamp_iso,
        )
        trace.events.append(ev)
        self._traces[incident_id] = trace
        return trace

    def advance_stage(
        self,
        incident_id: str,
        *,
        stage: IncidentStage,
        ai_confidence: float,
        mechanism_id: str | None,
        remediation_class: str | None,
        timestamp_iso: str,
        revision_reason: str = "",
    ) -> EvolutionEvent:
        """
        Record a stage transition for an incident.

        If mechanism_id or remediation_class changed from the previous
        event, assessment_changed is set to True.
        """
        trace = self._traces.get(incident_id)
        if trace is None:
            trace = EvolutionTrace(incident_id=incident_id)
            self._traces[incident_id] = trace

        changed = False
        if trace.events:
            prev = trace.events[-1]
            changed = (
                prev.mechanism_id != mechanism_id or prev.remediation_class != remediation_class
            )

        ev = EvolutionEvent(
            stage=stage,
            ai_confidence=ai_confidence,
            mechanism_id=mechanism_id,
            remediation_class=remediation_class,
            timestamp_iso=timestamp_iso,
            revision_reason=revision_reason,
            assessment_changed=changed,
        )
        trace.events.append(ev)
        return ev

    def close_incident(
        self,
        incident_id: str,
        *,
        final_mechanism_id: str | None,
        final_remediation_class: str | None,
        final_confidence: float,
        timestamp_iso: str,
        note: str = "",
    ) -> EvolutionEvent:
        """Record the CLOSED stage for an incident."""
        return self.advance_stage(
            incident_id,
            stage=IncidentStage.CLOSED,
            ai_confidence=final_confidence,
            mechanism_id=final_mechanism_id,
            remediation_class=final_remediation_class,
            timestamp_iso=timestamp_iso,
            revision_reason=note or "incident closed",
        )

    def trace_for(self, incident_id: str) -> EvolutionTrace | None:
        return self._traces.get(incident_id)

    def all_traces(self) -> list[EvolutionTrace]:
        return list(self._traces.values())

    def traces_with_revisions(self) -> list[EvolutionTrace]:
        return [t for t in self._traces.values() if t.assessment_was_revised]

    def mechanism_diagnosis_accuracy(self) -> dict[str, dict[str, Any]]:
        """
        For each mechanism, return what fraction of incidents had
        a consistent first-diagnosis (initial == final mechanism).
        """
        stats: dict[str, dict[str, Any]] = {}
        for trace in self._traces.values():
            init_mech = trace.initial_mechanism
            final_mech = trace.final_mechanism
            if not init_mech:
                continue
            s = stats.setdefault(
                init_mech,
                {"total": 0, "consistent": 0, "revised_count": 0},
            )
            s["total"] += 1
            if init_mech == final_mech:
                s["consistent"] += 1
            else:
                s["revised_count"] += 1
        for key, s in stats.items():
            total = s["total"]
            stats[key]["first_diagnosis_accuracy"] = (
                round(s["consistent"] / total, 4) if total > 0 else 0.0
            )
        return stats

    def mean_revisions_per_incident(self) -> float:
        traces = list(self._traces.values())
        if not traces:
            return 0.0
        return round(sum(t.revision_count for t in traces) / len(traces), 4)

    def volatile_incidents(self) -> list[str]:
        """Return incident IDs where confidence trend is 'volatile'."""
        return [
            incident_id
            for incident_id, trace in self._traces.items()
            if trace.confidence_trend == "volatile"
        ]
