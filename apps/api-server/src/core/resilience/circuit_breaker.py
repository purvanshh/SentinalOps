"""
Circuit breaker for LLM provider calls.

States:
  CLOSED  - Normal operation, requests pass through
  OPEN    - Provider is failing, requests are rejected immediately
  HALF_OPEN - Testing if provider has recovered

Prevents cascading failures and reduces load on failing providers.
"""

from __future__ import annotations

import time
from enum import Enum
from threading import Lock
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """
    Per-provider circuit breaker.

    Parameters:
        failure_threshold: Number of consecutive failures before opening
        recovery_timeout: Seconds to wait before attempting recovery (half-open)
        half_open_max_calls: Max calls allowed in half-open state to test recovery
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 1,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float = 0.0
        self._half_open_calls = 0
        self._lock = Lock()
        self._total_failures = 0
        self._total_successes = 0

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                # Check if recovery timeout has elapsed
                if time.time() - self._last_failure_time >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    logger.info("circuit_breaker_half_open", provider=self.name)
            return self._state

    @property
    def is_available(self) -> bool:
        """Check if the circuit allows requests."""
        current_state = self.state
        if current_state == CircuitState.CLOSED:
            return True
        if current_state == CircuitState.HALF_OPEN:
            with self._lock:
                return self._half_open_calls < self.half_open_max_calls
        return False

    def record_success(self) -> None:
        """Record a successful call."""
        with self._lock:
            self._total_successes += 1
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.half_open_max_calls:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
                    logger.info("circuit_breaker_closed", provider=self.name)
            else:
                self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed call."""
        with self._lock:
            self._failure_count += 1
            self._total_failures += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                # Failed during recovery test, reopen
                self._state = CircuitState.OPEN
                self._half_open_calls = 0
                logger.warning("circuit_breaker_reopened", provider=self.name)
            elif self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    "circuit_breaker_opened",
                    provider=self.name,
                    failure_count=self._failure_count,
                )

    def record_call_attempt(self) -> None:
        """Record that a call attempt is being made (for half-open tracking)."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_calls += 1

    def trip(self) -> None:
        """Immediately open the circuit after a non-retriable provider failure."""
        with self._lock:
            self._failure_count = max(self._failure_count + 1, self.failure_threshold)
            self._total_failures += 1
            self._success_count = 0
            self._half_open_calls = 0
            self._last_failure_time = time.time()
            self._state = CircuitState.OPEN
            logger.warning("circuit_breaker_tripped", provider=self.name)

    def force_open(self) -> None:
        """Manually open the circuit."""
        with self._lock:
            self._state = CircuitState.OPEN
            self._last_failure_time = time.time()

    def force_close(self) -> None:
        """Manually close the circuit (reset)."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._half_open_calls = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "total_failures": self._total_failures,
            "total_successes": self._total_successes,
            "last_failure_time": self._last_failure_time,
            "is_available": self.is_available,
        }

# Enhanced with fallback activations metrics monitoring.
