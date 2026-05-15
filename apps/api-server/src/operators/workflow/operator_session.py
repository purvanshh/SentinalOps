from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class SessionPhase(Enum):
    INITIAL = "INITIAL"
    ACTIVE = "ACTIVE"
    OVERLOADED = "OVERLOADED"
    FATIGUED = "FATIGUED"
    RECOVERING = "RECOVERING"
    COMPLETED = "COMPLETED"


@dataclass
class OperatorSession:
    session_id: str
    operator_id: str
    start_time_iso: str
    phase: SessionPhase
    incidents_handled: int
    overrides_issued: int
    escalations_triggered: int
    false_positives_encountered: int
    total_response_time_seconds: float
    context_switches: int


def _compute_phase(session: OperatorSession) -> SessionPhase:
    if session.phase == SessionPhase.COMPLETED:
        return SessionPhase.COMPLETED

    incidents = session.incidents_handled
    override_rate = session.overrides_issued / incidents if incidents > 0 else 0.0

    if incidents > 8:
        return SessionPhase.FATIGUED
    if incidents > 5 and override_rate > 0.5:
        return SessionPhase.OVERLOADED
    if incidents > 0:
        return SessionPhase.ACTIVE
    return SessionPhase.INITIAL


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, OperatorSession] = {}
        self._last_incident: dict[str, str | None] = {}

    def create_session(self, operator_id: str) -> OperatorSession:
        session_id = str(uuid.uuid4())
        session = OperatorSession(
            session_id=session_id,
            operator_id=operator_id,
            start_time_iso=datetime.now(tz=timezone.utc).isoformat(),
            phase=SessionPhase.INITIAL,
            incidents_handled=0,
            overrides_issued=0,
            escalations_triggered=0,
            false_positives_encountered=0,
            total_response_time_seconds=0.0,
            context_switches=0,
        )
        self._sessions[session_id] = session
        return session

    def _get(self, session_id: str) -> OperatorSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Session not found: {session_id}")
        return session

    def handle_incident(
        self,
        session_id: str,
        incident: dict,
        response_time_seconds: float,
    ) -> OperatorSession:
        session = self._get(session_id)

        prev_incident_id = self._last_incident.get(session_id)
        current_incident_id = incident.get("id")

        if prev_incident_id is not None and prev_incident_id != current_incident_id:
            session.context_switches += 1

        self._last_incident[session_id] = current_incident_id

        session.incidents_handled += 1
        session.total_response_time_seconds += response_time_seconds
        session.phase = _compute_phase(session)
        return session

    def record_override(self, session_id: str) -> None:
        session = self._get(session_id)
        session.overrides_issued += 1
        session.phase = _compute_phase(session)

    def record_escalation(self, session_id: str) -> None:
        session = self._get(session_id)
        session.escalations_triggered += 1
        session.phase = _compute_phase(session)

    def record_false_positive(self, session_id: str) -> None:
        session = self._get(session_id)
        session.false_positives_encountered += 1
        session.phase = _compute_phase(session)

    def get_session_phase(self, session_id: str) -> SessionPhase:
        return self._get(session_id).phase

    def close_session(self, session_id: str) -> OperatorSession:
        session = self._get(session_id)
        session.phase = SessionPhase.COMPLETED
        return session
