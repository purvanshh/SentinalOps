from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class DecisionStage(Enum):
    RECOMMENDATION_RECEIVED = "RECOMMENDATION_RECEIVED"
    OPERATOR_REVIEW_STARTED = "OPERATOR_REVIEW_STARTED"
    ESCALATION_TRIGGERED = "ESCALATION_TRIGGERED"
    OVERRIDE_APPLIED = "OVERRIDE_APPLIED"
    REMEDIATION_EXECUTED = "REMEDIATION_EXECUTED"
    ROLLBACK_TRIGGERED = "ROLLBACK_TRIGGERED"
    POST_EXECUTION_REVIEW = "POST_EXECUTION_REVIEW"
    INCIDENT_CLOSED = "INCIDENT_CLOSED"


_TERMINAL_STAGES: frozenset[DecisionStage] = frozenset(
    {DecisionStage.INCIDENT_CLOSED, DecisionStage.ROLLBACK_TRIGGERED}
)


@dataclass
class DecisionEvent:
    stage: DecisionStage
    timestamp_iso: str
    incident_id: str
    elapsed_seconds: float
    metadata: dict


@dataclass
class DecisionLifecycle:
    incident_id: str
    events: list[DecisionEvent]
    is_complete: bool
    final_stage: DecisionStage | None
    total_elapsed_seconds: float


class DecisionLifecycleTracker:
    def __init__(self) -> None:
        self._lifecycles: dict[str, list[DecisionEvent]] = {}

    def record_event(
        self,
        incident_id: str,
        stage: DecisionStage,
        elapsed_seconds: float,
        metadata: dict | None = None,
    ) -> DecisionEvent:
        event = DecisionEvent(
            stage=stage,
            timestamp_iso=datetime.now(tz=timezone.utc).isoformat(),
            incident_id=incident_id,
            elapsed_seconds=elapsed_seconds,
            metadata=metadata or {},
        )
        self._lifecycles.setdefault(incident_id, []).append(event)
        return event

    def get_lifecycle(self, incident_id: str) -> DecisionLifecycle:
        events = self._lifecycles.get(incident_id, [])
        final_stage: DecisionStage | None = events[-1].stage if events else None
        is_complete = final_stage in _TERMINAL_STAGES if final_stage is not None else False
        total_elapsed = events[-1].elapsed_seconds if events else 0.0
        return DecisionLifecycle(
            incident_id=incident_id,
            events=list(events),
            is_complete=is_complete,
            final_stage=final_stage,
            total_elapsed_seconds=total_elapsed,
        )

    def all_lifecycles(self) -> list[DecisionLifecycle]:
        return [self.get_lifecycle(iid) for iid in self._lifecycles]

    def mean_time_to_stage(self, stage: DecisionStage) -> float | None:
        times: list[float] = []
        for events in self._lifecycles.values():
            for event in events:
                if event.stage == stage:
                    times.append(event.elapsed_seconds)
                    break
        if not times:
            return None
        return sum(times) / len(times)
