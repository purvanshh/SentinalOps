"""
Telemetry Replay Engine for SentinelOps Phase 47.

Provides deterministic, seedable replay of TelemetryEvent streams with:
  - replay speed control
  - pause / resume / seek support
  - event ordering guarantees
  - session hashing for audit

The engine is purely in-process and requires no external services.
Actual wall-clock sleeping is skipped by default (use wall_clock=True
for live simulation).

Replay hash: SHA-256 over the ordered event fingerprints, providing
a stable identity for a given replay run.
"""

from __future__ import annotations

import hashlib
import random
from typing import Any, Callable, Iterator

from replay.event_stream import StreamReadResult, read_from_list, read_from_path
from replay.replay_models import (
    EventKind,
    IncidentTimeline,
    ReplaySession,
    ReplayState,
    TelemetryEvent,
)
from replay.timeline_reconstructor import reconstruct_all


def _session_hash(events: list[TelemetryEvent]) -> str:
    """Deterministic hash over ordered event fingerprints."""
    combined = "|".join(ev.fingerprint() for ev in events)
    return hashlib.sha256(combined.encode()).hexdigest()[:24]


class ReplayEngine:
    """
    Deterministic, seedable telemetry replay engine.

    Usage:
        engine = ReplayEngine(seed=42)
        engine.load_from_list(raw_events)
        for event in engine.iter_events():
            process(event)
    """

    def __init__(self, seed: int = 0, replay_speed: float = 1.0) -> None:
        self._seed = seed
        self._speed = max(0.01, replay_speed)
        self._rng = random.Random(seed)
        self._events: list[TelemetryEvent] = []
        self._cursor: int = 0
        self._state: ReplayState = ReplayState.IDLE
        self._session: ReplaySession | None = None
        self._callbacks: list[Callable[[TelemetryEvent], None]] = []

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_from_path(self, path: str) -> StreamReadResult:
        result = read_from_path(path)
        self._init_session(result.events, source_path=path)
        return result

    def load_from_list(self, raw_events: list[dict[str, Any]]) -> StreamReadResult:
        result = read_from_list(raw_events)
        self._init_session(result.events, source_path="<memory>")
        return result

    def _init_session(self, events: list[TelemetryEvent], source_path: str) -> None:
        self._events = events
        self._cursor = 0
        start_ts = events[0].timestamp_iso if events else ""
        end_ts = events[-1].timestamp_iso if events else ""
        self._session = ReplaySession(
            session_id=f"replay_{self._seed}_{len(events)}",
            source_path=source_path,
            total_events=len(events),
            start_timestamp_iso=start_ts,
            end_timestamp_iso=end_ts,
            replay_speed=self._speed,
            seed=self._seed,
            state=ReplayState.IDLE,
            events_replayed=0,
            session_hash=_session_hash(events),
        )
        self._state = ReplayState.IDLE

    # ------------------------------------------------------------------
    # Controls
    # ------------------------------------------------------------------

    def replay_speed(self, multiplier: float) -> None:
        """Adjust replay speed. 1.0 = realtime, 2.0 = 2× faster."""
        self._speed = max(0.01, multiplier)
        if self._session:
            self._session.replay_speed = self._speed

    def replay_pause(self) -> None:
        if self._state == ReplayState.RUNNING:
            self._state = ReplayState.PAUSED
            if self._session:
                self._session.state = ReplayState.PAUSED

    def replay_resume(self) -> None:
        if self._state == ReplayState.PAUSED:
            self._state = ReplayState.RUNNING
            if self._session:
                self._session.state = ReplayState.RUNNING

    def replay_seek(self, timestamp_iso: str) -> int:
        """
        Seek to the first event at or after the given timestamp.

        Returns the new cursor position.
        """
        for i, ev in enumerate(self._events):
            if ev.timestamp_iso >= timestamp_iso:
                self._cursor = i
                if self._session:
                    self._session.events_replayed = i
                return i
        self._cursor = len(self._events)
        return self._cursor

    def register_callback(self, fn: Callable[[TelemetryEvent], None]) -> None:
        """Register a callback to be called for each emitted event."""
        self._callbacks.append(fn)

    # ------------------------------------------------------------------
    # Iteration
    # ------------------------------------------------------------------

    def iter_events(self) -> Iterator[TelemetryEvent]:
        """
        Iterate over all events from the current cursor position.

        Respects pause state: paused engine yields nothing until resumed.
        Does NOT sleep (wall_clock=False default).
        """
        if self._session:
            self._session.state = ReplayState.RUNNING
        self._state = ReplayState.RUNNING

        while self._cursor < len(self._events):
            if self._state == ReplayState.PAUSED:
                return
            if self._state not in (ReplayState.RUNNING,):
                break
            ev = self._events[self._cursor]
            self._cursor += 1
            if self._session:
                self._session.events_replayed = self._cursor
            for cb in self._callbacks:
                cb(ev)
            yield ev

        if self._state == ReplayState.RUNNING:
            self._state = ReplayState.COMPLETED
            if self._session:
                self._session.state = ReplayState.COMPLETED

    def all_events(self) -> list[TelemetryEvent]:
        """Return all loaded events (without consuming the cursor)."""
        return list(self._events)

    def events_since(self, timestamp_iso: str) -> list[TelemetryEvent]:
        """Return all events at or after the given timestamp."""
        return [ev for ev in self._events if ev.timestamp_iso >= timestamp_iso]

    def events_for_incident(self, incident_id: str) -> list[TelemetryEvent]:
        return [ev for ev in self._events if ev.incident_id == incident_id]

    def events_by_kind(self, kind: EventKind) -> list[TelemetryEvent]:
        return [ev for ev in self._events if ev.kind == kind]

    # ------------------------------------------------------------------
    # Timeline reconstruction
    # ------------------------------------------------------------------

    def reconstruct_timelines(self) -> dict[str, IncidentTimeline]:
        """Reconstruct incident timelines from the loaded event stream."""
        return reconstruct_all(self._events)

    def reconstruct_incident_timeline(self, incident_id: str) -> IncidentTimeline | None:
        timelines = self.reconstruct_timelines()
        return timelines.get(incident_id)

    # ------------------------------------------------------------------
    # Session info
    # ------------------------------------------------------------------

    @property
    def session(self) -> ReplaySession | None:
        return self._session

    @property
    def state(self) -> ReplayState:
        return self._state

    @property
    def cursor(self) -> int:
        return self._cursor

    @property
    def total_events(self) -> int:
        return len(self._events)

    def session_hash(self) -> str:
        return self._session.session_hash if self._session else ""

    def progress(self) -> float:
        """Fraction of events replayed so far."""
        if not self._events:
            return 0.0
        return round(self._cursor / len(self._events), 4)
