"""
Tests for the circuit breaker implementation.
"""

import time

from core.resilience.circuit_breaker import CircuitBreaker, CircuitState


class TestCircuitBreaker:
    def test_starts_closed(self):
        cb = CircuitBreaker("test", failure_threshold=3)
        assert cb.state == CircuitState.CLOSED
        assert cb.is_available is True

    def test_opens_after_threshold_failures(self):
        cb = CircuitBreaker("test", failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.is_available is False

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker("test", failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        cb.record_failure()
        cb.record_failure()
        # Should still be closed because success reset the count
        assert cb.state == CircuitState.CLOSED

    def test_transitions_to_half_open_after_recovery_timeout(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_success_closes_circuit(self):
        cb = CircuitBreaker(
            "test", failure_threshold=1, recovery_timeout=0.1, half_open_max_calls=1
        )
        cb.record_failure()
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_half_open_failure_reopens_circuit(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure()
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_force_open(self):
        cb = CircuitBreaker("test", failure_threshold=10)
        cb.force_open()
        assert cb.state == CircuitState.OPEN
        assert cb.is_available is False

    def test_force_close(self):
        cb = CircuitBreaker("test", failure_threshold=1)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        cb.force_close()
        assert cb.state == CircuitState.CLOSED
        assert cb.is_available is True

    def test_trip_opens_circuit_immediately(self):
        cb = CircuitBreaker("test", failure_threshold=3)
        cb.trip()
        assert cb.state == CircuitState.OPEN
        assert cb.is_available is False
        assert cb.to_dict()["failure_count"] == 3

    def test_to_dict(self):
        cb = CircuitBreaker("test_provider", failure_threshold=3)
        cb.record_failure()
        info = cb.to_dict()
        assert info["name"] == "test_provider"
        assert info["state"] == "CLOSED"
        assert info["failure_count"] == 1
        assert info["total_failures"] == 1
