"""
Operating mode management for SentinelOps AI.

Defines explicit runtime operating modes:
  FULL         - All providers available, normal operation
  DEGRADED     - Primary provider failed, using secondary
  LOCAL_ONLY   - Only local models (Ollama) available
  SAFE_MODE    - Only deterministic fallback, no LLM calls
  OBSERVE_ONLY - System records but takes no automated action

Modes are:
  - Visible in API responses
  - Persisted in graph state
  - Logged in observability
  - Automatically transitioned on provider failure
"""

from __future__ import annotations

import time
from enum import Enum
from threading import Lock
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class OperatingMode(str, Enum):
    FULL = "FULL"
    DEGRADED = "DEGRADED"
    LOCAL_ONLY = "LOCAL_ONLY"
    SAFE_MODE = "SAFE_MODE"
    OBSERVE_ONLY = "OBSERVE_ONLY"

    @property
    def allows_llm_calls(self) -> bool:
        return self in (OperatingMode.FULL, OperatingMode.DEGRADED, OperatingMode.LOCAL_ONLY)

    @property
    def allows_automated_actions(self) -> bool:
        return self in (OperatingMode.FULL, OperatingMode.DEGRADED, OperatingMode.LOCAL_ONLY, OperatingMode.SAFE_MODE)

    @property
    def is_degraded(self) -> bool:
        return self != OperatingMode.FULL


class ModeTransition:
    """Records a mode transition for audit trail."""

    def __init__(self, from_mode: OperatingMode, to_mode: OperatingMode, reason: str) -> None:
        self.from_mode = from_mode
        self.to_mode = to_mode
        self.reason = reason
        self.timestamp = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_mode": self.from_mode.value,
            "to_mode": self.to_mode.value,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


class OperatingModeManager:
    """
    Thread-safe singleton managing the current operating mode.

    Automatically transitions based on provider health signals.
    Maintains a history of transitions for observability.
    """

    _instance: OperatingModeManager | None = None
    _lock = Lock()

    def __new__(cls) -> OperatingModeManager:
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._mode = OperatingMode.FULL
        self._transitions: list[ModeTransition] = []
        self._mode_lock = Lock()
        self._last_transition_time: float = 0.0
        self._initialized = True

    @property
    def current_mode(self) -> OperatingMode:
        return self._mode

    @property
    def transitions(self) -> list[ModeTransition]:
        return list(self._transitions)

    def transition_to(self, new_mode: OperatingMode, reason: str) -> None:
        """Transition to a new operating mode with reason logging."""
        with self._mode_lock:
            if new_mode == self._mode:
                return

            old_mode = self._mode
            transition = ModeTransition(old_mode, new_mode, reason)
            self._transitions.append(transition)
            self._mode = new_mode
            self._last_transition_time = time.time()

            logger.warning(
                "operating_mode_transition",
                from_mode=old_mode.value,
                to_mode=new_mode.value,
                reason=reason,
            )

    def on_provider_failure(self, provider_name: str, layer: int) -> None:
        """React to a provider failure by potentially transitioning mode."""
        if layer == 1:
            # Primary failed, move to DEGRADED
            if self._mode == OperatingMode.FULL:
                self.transition_to(
                    OperatingMode.DEGRADED,
                    f"Primary provider '{provider_name}' failed",
                )
        elif layer == 2:
            # Secondary failed, move to LOCAL_ONLY
            if self._mode in (OperatingMode.FULL, OperatingMode.DEGRADED):
                self.transition_to(
                    OperatingMode.LOCAL_ONLY,
                    f"Secondary provider '{provider_name}' failed",
                )
        elif layer == 3:
            # Local model failed, move to SAFE_MODE
            if self._mode in (OperatingMode.FULL, OperatingMode.DEGRADED, OperatingMode.LOCAL_ONLY):
                self.transition_to(
                    OperatingMode.SAFE_MODE,
                    f"Local provider '{provider_name}' failed, using deterministic fallback",
                )

    def on_provider_recovery(self, provider_name: str, layer: int) -> None:
        """React to a provider recovery by potentially upgrading mode."""
        if layer == 1 and self._mode != OperatingMode.FULL:
            self.transition_to(
                OperatingMode.FULL,
                f"Primary provider '{provider_name}' recovered",
            )
        elif layer == 2 and self._mode in (OperatingMode.LOCAL_ONLY, OperatingMode.SAFE_MODE):
            self.transition_to(
                OperatingMode.DEGRADED,
                f"Secondary provider '{provider_name}' recovered",
            )
        elif layer == 3 and self._mode == OperatingMode.SAFE_MODE:
            self.transition_to(
                OperatingMode.LOCAL_ONLY,
                f"Local provider '{provider_name}' recovered",
            )

    def reset(self) -> None:
        """Reset to FULL mode (for testing or manual recovery)."""
        with self._mode_lock:
            self._mode = OperatingMode.FULL
            self._transitions.clear()
            self._last_transition_time = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize current state for API responses and state persistence."""
        return {
            "current_mode": self._mode.value,
            "is_degraded": self._mode.is_degraded,
            "allows_llm_calls": self._mode.allows_llm_calls,
            "allows_automated_actions": self._mode.allows_automated_actions,
            "last_transition_time": self._last_transition_time,
            "transition_count": len(self._transitions),
            "recent_transitions": [t.to_dict() for t in self._transitions[-5:]],
        }
