"""
Replay scheduler for SentinelOps Phase 47.

Determines when to trigger replay sessions based on drift signals,
evaluation cycle results, and configurable scheduling policies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from runtime.drift_monitor import DriftSignal


@dataclass
class ReplayTrigger:
    """Describes why a replay session was scheduled."""

    trigger_id: str
    reason: str  # "drift_detected", "calibration_error", "scheduled", "manual"
    priority: str  # "high", "normal", "low"
    triggered_at: str
    incident_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_high_priority(self) -> bool:
        return self.priority == "high"


@dataclass
class SchedulerStats:
    """Running statistics for the replay scheduler."""

    total_triggers: int
    drift_triggers: int
    calibration_triggers: int
    scheduled_triggers: int
    manual_triggers: int
    high_priority_triggers: int


class ReplayScheduler:
    """
    Schedules replay sessions based on drift signals and evaluation cycle output.

    Policies:
    - Drift with severity "high" → high-priority trigger
    - Drift with severity "medium" → normal-priority trigger
    - Calibration error > 0.15 → normal-priority trigger
    - Cycle count multiple of `scheduled_interval` → low-priority scheduled trigger
    """

    def __init__(self, scheduled_interval: int = 10) -> None:
        self._scheduled_interval = scheduled_interval
        self._triggers: list[ReplayTrigger] = []
        self._trigger_count = 0

    def evaluate_drift_signals(
        self,
        signals: list[DriftSignal],
        incident_ids: list[str] | None = None,
    ) -> list[ReplayTrigger]:
        """Convert drift signals into replay triggers."""
        new_triggers: list[ReplayTrigger] = []
        for signal in signals:
            priority = "high" if signal.severity == "high" else "normal"
            trigger = self._make_trigger(
                reason="drift_detected",
                priority=priority,
                incident_ids=incident_ids or [],
                metadata={"signal_kind": signal.kind, "delta": signal.delta},
            )
            new_triggers.append(trigger)
        return new_triggers

    def evaluate_calibration_error(
        self,
        calibration_error: float,
        threshold: float = 0.15,
        incident_ids: list[str] | None = None,
    ) -> ReplayTrigger | None:
        """Trigger a replay if calibration error exceeds threshold."""
        if calibration_error <= threshold:
            return None
        return self._make_trigger(
            reason="calibration_error",
            priority="normal",
            incident_ids=incident_ids or [],
            metadata={"calibration_error": calibration_error},
        )

    def evaluate_cycle(
        self,
        cycle_id: int,
        calibration_error: float = 0.0,
        drift_signals: list[DriftSignal] | None = None,
        incident_ids: list[str] | None = None,
    ) -> list[ReplayTrigger]:
        """Evaluate a completed evaluation cycle and return any triggered replays."""
        triggers: list[ReplayTrigger] = []

        if drift_signals:
            triggers.extend(self.evaluate_drift_signals(drift_signals, incident_ids=incident_ids))

        cal_trigger = self.evaluate_calibration_error(calibration_error, incident_ids=incident_ids)
        if cal_trigger:
            triggers.append(cal_trigger)

        if self._scheduled_interval > 0 and cycle_id % self._scheduled_interval == 0:
            triggers.append(
                self._make_trigger(
                    reason="scheduled",
                    priority="low",
                    incident_ids=incident_ids or [],
                    metadata={"cycle_id": cycle_id},
                )
            )

        return triggers

    def schedule_manual(
        self,
        incident_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ReplayTrigger:
        """Manually schedule a replay session."""
        return self._make_trigger(
            reason="manual",
            priority="high",
            incident_ids=incident_ids or [],
            metadata=metadata or {},
        )

    def all_triggers(self) -> list[ReplayTrigger]:
        return list(self._triggers)

    def stats(self) -> SchedulerStats:
        return SchedulerStats(
            total_triggers=len(self._triggers),
            drift_triggers=sum(1 for t in self._triggers if t.reason == "drift_detected"),
            calibration_triggers=sum(1 for t in self._triggers if t.reason == "calibration_error"),
            scheduled_triggers=sum(1 for t in self._triggers if t.reason == "scheduled"),
            manual_triggers=sum(1 for t in self._triggers if t.reason == "manual"),
            high_priority_triggers=sum(1 for t in self._triggers if t.is_high_priority),
        )

    def clear(self) -> None:
        self._triggers.clear()
        self._trigger_count = 0

    # ------------------------------------------------------------------

    def _make_trigger(
        self,
        reason: str,
        priority: str,
        incident_ids: list[str],
        metadata: dict[str, Any],
    ) -> ReplayTrigger:
        self._trigger_count += 1
        trigger = ReplayTrigger(
            trigger_id=f"rt_{self._trigger_count:05d}",
            reason=reason,
            priority=priority,
            triggered_at=datetime.now(timezone.utc).isoformat(),
            incident_ids=incident_ids,
            metadata=metadata,
        )
        self._triggers.append(trigger)
        return trigger
