"""
Resilient LLM client that integrates the provider chain with the fallback classifier.

This replaces direct LLMClient usage in the router node, providing:
  - Multi-layer provider failover
  - Automatic fallback to deterministic classification
  - Operating mode awareness
  - Full failure transparency
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import structlog
from core.config import get_settings
from core.resilience.fallback_classifier import (
    DeterministicFallbackClassifier,
    FallbackClassification,
)
from core.resilience.operating_mode import OperatingMode, OperatingModeManager
from core.resilience.provider_chain import ProviderChain, ProviderChainResult, ProviderConfig
from core.runtime_context import live_provider_access_allowed
from pydantic import BaseModel

logger = structlog.get_logger(__name__)


def build_provider_chain_from_settings() -> ProviderChain:
    """
    Build the provider chain from environment settings.

    Layer 1: Primary (configured LLM_BASE_URL / LLM_MODEL)
    Layer 2: Secondary (LLM_SECONDARY_BASE_URL / LLM_SECONDARY_MODEL,
    falls back to primary with different model)
    Layer 3: Local Ollama (localhost:11434)
    """
    settings = get_settings()

    providers: list[ProviderConfig] = []

    # Layer 1: Primary provider
    providers.append(
        ProviderConfig(
            name="primary",
            layer=1,
            base_url=settings.resolved_llm_base_url,
            api_key=settings.resolved_llm_api_key,
            model=settings.resolved_llm_model,
            timeout=15.0,
            max_retries=1,
            initial_backoff=0.5,
            max_backoff=2.0,
            circuit_breaker_threshold=3,
            circuit_breaker_recovery=30.0,
        )
    )

    # Layer 2: Secondary provider is opt-in to avoid accidental model drift
    # between heterogeneous OpenAI-compatible endpoints.
    secondary_configured = any(
        [
            settings.llm_secondary_base_url,
            settings.llm_secondary_api_key,
            settings.llm_secondary_model,
        ]
    )
    secondary_base_url = settings.llm_secondary_base_url or settings.resolved_llm_base_url
    secondary_api_key = settings.llm_secondary_api_key or settings.resolved_llm_api_key
    secondary_model = settings.llm_secondary_model or settings.resolved_llm_model

    if secondary_configured:
        providers.append(
            ProviderConfig(
                name="secondary",
                layer=2,
                base_url=secondary_base_url,
                api_key=secondary_api_key,
                model=secondary_model,
                timeout=12.0,
                max_retries=1,
                initial_backoff=0.5,
                max_backoff=2.0,
                circuit_breaker_threshold=3,
                circuit_breaker_recovery=20.0,
            )
        )

    # Layer 3: Local Ollama (always available as fallback)
    local_base_url = getattr(settings, "llm_local_base_url", None) or "http://localhost:11434/v1"
    local_model = getattr(settings, "llm_local_model", None) or "llama3.2"

    providers.append(
        ProviderConfig(
            name="local_ollama",
            layer=3,
            base_url=local_base_url,
            api_key="ollama",  # Ollama doesn't require a real key
            model=local_model,
            timeout=15.0,
            max_retries=0,
            initial_backoff=0.5,
            max_backoff=2.0,
            circuit_breaker_threshold=5,  # More lenient for local
            circuit_breaker_recovery=15.0,
        )
    )

    return ProviderChain(providers)


# Module-level singleton
_PROVIDER_CHAIN: ProviderChain | None = None
_FALLBACK_CLASSIFIER: DeterministicFallbackClassifier | None = None


def get_provider_chain() -> ProviderChain:
    """Get or create the singleton provider chain."""
    global _PROVIDER_CHAIN
    if not live_provider_access_allowed():
        raise RuntimeError(
            "Live provider chains are disabled in evaluation mode. Use injected mocks instead."
        )
    if _PROVIDER_CHAIN is None:
        _PROVIDER_CHAIN = build_provider_chain_from_settings()
    return _PROVIDER_CHAIN


def get_fallback_classifier() -> DeterministicFallbackClassifier:
    """Get or create the singleton fallback classifier."""
    global _FALLBACK_CLASSIFIER
    if _FALLBACK_CLASSIFIER is None:
        _FALLBACK_CLASSIFIER = DeterministicFallbackClassifier()
    return _FALLBACK_CLASSIFIER


class ResilientLLMClient:
    """
    High-level resilient LLM client.

    Wraps the provider chain and deterministic fallback into a single interface.
    Provides full transparency about which path was taken.
    """

    def __init__(
        self,
        provider_chain: ProviderChain | None = None,
        fallback_classifier: DeterministicFallbackClassifier | None = None,
    ) -> None:
        self._chain = provider_chain or get_provider_chain()
        self._fallback = fallback_classifier or get_fallback_classifier()
        self._mode_manager = OperatingModeManager()

    @property
    def operating_mode(self) -> OperatingMode:
        return self._mode_manager.current_mode

    async def generate(
        self,
        messages: Sequence[dict[str, Any]],
        *,
        temperature: float = 0.1,
        structured_output_model: type[BaseModel] | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> tuple[BaseModel | dict[str, Any], ProviderChainResult]:
        """
        Generate a response using the provider chain.

        Returns:
            Tuple of (response, chain_result) where chain_result contains
            full transparency metadata about the path taken.

        Raises:
            Never raises for provider failures - always returns a result
            (either from a provider or from the deterministic fallback).
            Only raises if the structured_output_model parsing fails on
            a successful provider response.
        """
        # If we're in SAFE_MODE or OBSERVE_ONLY, skip LLM calls entirely
        if not self._mode_manager.current_mode.allows_llm_calls:
            logger.info(
                "llm_calls_disabled_by_mode",
                mode=self._mode_manager.current_mode.value,
            )
            return self._make_safe_mode_result()

        # Try the provider chain
        chain_result = await self._chain.generate(
            messages,
            temperature=temperature,
            structured_output_model=structured_output_model,
            tools=tools,
        )

        if chain_result.response is not None:
            return chain_result.response, chain_result

        # All providers exhausted - this is handled by the caller
        # who should use the fallback classifier for classification tasks
        return None, chain_result  # type: ignore[return-value]

    async def classify_with_fallback(
        self,
        messages: Sequence[dict[str, Any]],
        alert_payload: dict[str, Any],
        *,
        structured_output_model: type[BaseModel] | None = None,
        temperature: float = 0.1,
    ) -> tuple[BaseModel | FallbackClassification, ProviderChainResult]:
        """
        Classify an incident with automatic fallback to deterministic classifier.

        This is the primary method for the router node. It guarantees a classification
        result even if all LLM providers are down.
        """
        # Try LLM providers first
        response, chain_result = await self.generate(
            messages,
            temperature=temperature,
            structured_output_model=structured_output_model,
        )

        if response is not None:
            return response, chain_result

        # Layer 4: Deterministic fallback
        logger.warning(
            "activating_deterministic_fallback",
            incident_payload_keys=list(alert_payload.keys()),
        )
        fallback_result = self._fallback.classify(alert_payload)

        # Update chain result to reflect fallback usage
        chain_result = ProviderChainResult(
            response=fallback_result,
            provider_used="deterministic_fallback",
            layer_used=4,
            operating_mode=self._mode_manager.current_mode,
            attempts=chain_result.attempts,
            fallback_activated=True,
            total_latency_ms=chain_result.total_latency_ms,
            provider_health=chain_result.provider_health,
        )

        return fallback_result, chain_result

    def _make_safe_mode_result(self) -> tuple[None, ProviderChainResult]:
        """Create a result indicating safe mode prevented LLM calls."""
        return None, ProviderChainResult(
            response=None,
            provider_used="none_safe_mode",
            layer_used=0,
            operating_mode=self._mode_manager.current_mode,
            attempts=[],
            fallback_activated=True,
            total_latency_ms=0.0,
            provider_health=self._chain.get_health(),
        )

    def get_health(self) -> dict[str, Any]:
        """Get health status of the resilient client."""
        return {
            "operating_mode": self._mode_manager.to_dict(),
            "provider_chain": self._chain.get_health(),
        }

    async def close(self) -> None:
        """Cleanup (no-op for now, providers use per-request clients)."""
        pass
