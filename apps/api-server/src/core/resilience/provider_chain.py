"""
Multi-layer provider fallback chain.

Fallback order:
  Layer 1: Primary provider/model (e.g., OpenAI GPT-4)
  Layer 2: Secondary provider/model (e.g., OpenAI GPT-3.5 or Anthropic)
  Layer 3: Local Ollama/OpenAI-compatible model
  Layer 4: Deterministic fallback classifier (zero dependencies)

The workflow continues unless ALL layers fail.
Includes exponential backoff, retry budgets, timeout handling,
and circuit breakers per provider.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import httpx
import structlog
from pydantic import BaseModel

from core.resilience.circuit_breaker import CircuitBreaker
from core.resilience.operating_mode import OperatingMode, OperatingModeManager

logger = structlog.get_logger(__name__)


@dataclass
class ProviderConfig:
    """Configuration for a single LLM provider in the chain."""

    name: str
    layer: int  # 1=primary, 2=secondary, 3=local
    base_url: str
    api_key: str
    model: str
    timeout: float = 30.0
    max_retries: int = 2
    initial_backoff: float = 1.0
    max_backoff: float = 16.0
    backoff_multiplier: float = 2.0
    circuit_breaker_threshold: int = 3
    circuit_breaker_recovery: float = 30.0


@dataclass
class ProviderAttempt:
    """Records a single provider attempt for transparency."""

    provider_name: str
    layer: int
    success: bool
    error: str | None = None
    latency_ms: float = 0.0
    retry_count: int = 0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_name": self.provider_name,
            "layer": self.layer,
            "success": self.success,
            "error": self.error,
            "latency_ms": round(self.latency_ms, 2),
            "retry_count": self.retry_count,
            "timestamp": self.timestamp,
        }


@dataclass
class ProviderChainResult:
    """Result from the provider chain, including transparency metadata."""

    response: BaseModel | dict[str, Any] | None
    provider_used: str
    layer_used: int
    operating_mode: OperatingMode
    attempts: list[ProviderAttempt] = field(default_factory=list)
    fallback_activated: bool = False
    total_latency_ms: float = 0.0
    provider_health: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_used": self.provider_used,
            "layer_used": self.layer_used,
            "operating_mode": self.operating_mode.value,
            "fallback_activated": self.fallback_activated,
            "total_latency_ms": round(self.total_latency_ms, 2),
            "attempt_count": len(self.attempts),
            "attempts": [a.to_dict() for a in self.attempts],
            "provider_health": self.provider_health,
        }


class ProviderChain:
    """
    Multi-layer provider failover chain with circuit breakers.

    Tries providers in order (layer 1 → 2 → 3).
    Each provider has its own circuit breaker and retry budget.
    If all providers fail, returns None (caller should use Layer 4 deterministic fallback).
    """

    def __init__(self, providers: list[ProviderConfig]) -> None:
        # Sort by layer
        self._providers = sorted(providers, key=lambda p: p.layer)
        self._circuit_breakers: dict[str, CircuitBreaker] = {}
        self._mode_manager = OperatingModeManager()

        for provider in self._providers:
            self._circuit_breakers[provider.name] = CircuitBreaker(
                name=provider.name,
                failure_threshold=provider.circuit_breaker_threshold,
                recovery_timeout=provider.circuit_breaker_recovery,
            )

    @property
    def mode_manager(self) -> OperatingModeManager:
        return self._mode_manager

    async def generate(
        self,
        messages: Sequence[dict[str, Any]],
        *,
        temperature: float = 0.1,
        structured_output_model: type[BaseModel] | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> ProviderChainResult:
        """
        Attempt generation through the provider chain.

        Returns ProviderChainResult with response=None if all providers exhausted.
        Caller is responsible for activating Layer 4 (deterministic fallback).
        """
        start_time = time.time()
        attempts: list[ProviderAttempt] = []

        for provider in self._providers:
            cb = self._circuit_breakers[provider.name]

            # Skip if circuit is open
            if not cb.is_available:
                attempts.append(ProviderAttempt(
                    provider_name=provider.name,
                    layer=provider.layer,
                    success=False,
                    error="circuit_breaker_open",
                ))
                logger.info(
                    "provider_skipped_circuit_open",
                    provider=provider.name,
                    layer=provider.layer,
                )
                continue

            # Try this provider with retries and exponential backoff
            attempt = await self._try_provider(provider, cb, messages, temperature, tools, structured_output_model)
            attempts.append(attempt)

            if attempt.success:
                # Provider succeeded
                self._mode_manager.on_provider_recovery(provider.name, provider.layer)
                total_latency = (time.time() - start_time) * 1000
                return ProviderChainResult(
                    response=attempt._response,  # type: ignore[attr-defined]
                    provider_used=provider.name,
                    layer_used=provider.layer,
                    operating_mode=self._mode_manager.current_mode,
                    attempts=attempts,
                    fallback_activated=provider.layer > 1,
                    total_latency_ms=total_latency,
                    provider_health=self.get_health(),
                )
            else:
                # Provider failed, signal mode manager
                self._mode_manager.on_provider_failure(provider.name, provider.layer)

        # All providers exhausted
        total_latency = (time.time() - start_time) * 1000
        logger.error(
            "all_providers_exhausted",
            attempt_count=len(attempts),
            total_latency_ms=total_latency,
        )

        return ProviderChainResult(
            response=None,
            provider_used="none",
            layer_used=0,
            operating_mode=self._mode_manager.current_mode,
            attempts=attempts,
            fallback_activated=True,
            total_latency_ms=total_latency,
            provider_health=self.get_health(),
        )

    async def _try_provider(
        self,
        provider: ProviderConfig,
        cb: CircuitBreaker,
        messages: Sequence[dict[str, Any]],
        temperature: float,
        tools: list[dict[str, Any]] | None,
        structured_output_model: type[BaseModel] | None,
    ) -> ProviderAttempt:
        """Try a single provider with retries and exponential backoff."""
        backoff = provider.initial_backoff
        last_error: str | None = None
        attempt_start = time.time()
        retry_count = 0

        for attempt_num in range(provider.max_retries + 1):
            try:
                cb.record_call_attempt()
                response = await self._call_provider(
                    provider, messages, temperature, tools, structured_output_model
                )
                cb.record_success()

                result = ProviderAttempt(
                    provider_name=provider.name,
                    layer=provider.layer,
                    success=True,
                    latency_ms=(time.time() - attempt_start) * 1000,
                    retry_count=retry_count,
                )
                # Attach response as private attr for chain to extract
                result._response = response  # type: ignore[attr-defined]

                logger.info(
                    "provider_call_success",
                    provider=provider.name,
                    layer=provider.layer,
                    retry_count=retry_count,
                    latency_ms=result.latency_ms,
                )
                return result

            except Exception as exc:
                retry_count = attempt_num + 1
                last_error = f"{type(exc).__name__}: {exc}"
                cb.record_failure()

                logger.warning(
                    "provider_call_failed",
                    provider=provider.name,
                    layer=provider.layer,
                    attempt=attempt_num + 1,
                    max_retries=provider.max_retries,
                    error=last_error,
                )

                # Don't backoff after the last attempt
                if attempt_num < provider.max_retries:
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * provider.backoff_multiplier, provider.max_backoff)

        return ProviderAttempt(
            provider_name=provider.name,
            layer=provider.layer,
            success=False,
            error=last_error,
            latency_ms=(time.time() - attempt_start) * 1000,
            retry_count=retry_count,
        )

    async def _call_provider(
        self,
        provider: ProviderConfig,
        messages: Sequence[dict[str, Any]],
        temperature: float,
        tools: list[dict[str, Any]] | None,
        structured_output_model: type[BaseModel] | None,
    ) -> BaseModel | dict[str, Any]:
        """Make the actual HTTP call to a provider."""
        import json

        payload: dict[str, Any] = {
            "model": provider.model,
            "messages": list(messages),
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        async with httpx.AsyncClient(
            base_url=provider.base_url.rstrip("/"),
            timeout=provider.timeout,
            headers={
                "Authorization": f"Bearer {provider.api_key}",
                "Content-Type": "application/json",
            },
        ) as client:
            response = await client.post("/chat/completions", json=payload)

            # Specific handling for 429 Too Many Requests
            if response.status_code == 429:
                raise ProviderRateLimitError(
                    f"Provider {provider.name} returned 429 Too Many Requests"
                )

            response.raise_for_status()
            body = response.json()
            message = body["choices"][0]["message"]

            if structured_output_model is None:
                return message

            content = message.get("content", "")
            if isinstance(content, list):
                text_content = "".join(
                    part.get("text", "") for part in content if isinstance(part, dict)
                ).strip()
            else:
                text_content = content.strip()

            parsed = json.loads(text_content)
            return structured_output_model.model_validate(parsed)

    def get_health(self) -> dict[str, Any]:
        """Get health status of all providers in the chain."""
        return {
            "operating_mode": self._mode_manager.current_mode.value,
            "providers": {
                provider.name: self._circuit_breakers[provider.name].to_dict()
                for provider in self._providers
            },
        }


class ProviderRateLimitError(Exception):
    """Raised when a provider returns 429 Too Many Requests."""
    pass
