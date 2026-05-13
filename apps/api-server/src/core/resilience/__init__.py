"""
Resilience module for SentinelOps AI.

Provides deterministic fallback classification, provider failover chains,
circuit breakers, and degraded execution mode management.
"""

from core.resilience.circuit_breaker import CircuitBreaker, CircuitState
from core.resilience.fallback_classifier import DeterministicFallbackClassifier
from core.resilience.operating_mode import OperatingMode, OperatingModeManager
from core.resilience.provider_chain import ProviderChain, ProviderConfig

__all__ = [
    "CircuitBreaker",
    "CircuitState",
    "DeterministicFallbackClassifier",
    "OperatingMode",
    "OperatingModeManager",
    "ProviderChain",
    "ProviderConfig",
]
