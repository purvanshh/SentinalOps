"""
Integration test: Incident lifecycle survivability under provider failure.

This test proves that:
1. An incident can be classified even when ALL LLM providers return 429
2. The deterministic fallback classifier activates automatically
3. The operating mode transitions correctly
4. Full failure transparency is maintained in the result
5. The pipeline does NOT silently fail or leave incidents in limbo

This is the PROOF that the resilience implementation works.
"""

import pytest
import respx
import httpx

from core.resilience.fallback_classifier import (
    DeterministicFallbackClassifier,
    FallbackClassification,
)
from core.resilience.operating_mode import OperatingMode, OperatingModeManager
from core.resilience.provider_chain import ProviderChain, ProviderConfig
from core.resilience.resilient_llm_client import ResilientLLMClient
from agents.router_agent.output_schema import RouterOutput


@pytest.fixture(autouse=True)
def reset_mode():
    manager = OperatingModeManager()
    manager.reset()
    yield
    manager.reset()


def _make_all_failing_providers() -> list[ProviderConfig]:
    """Create providers that will all fail with 429."""
    return [
        ProviderConfig(
            name="openai_primary",
            layer=1,
            base_url="http://openai-primary.test/v1",
            api_key="sk-test",
            model="gpt-4",
            timeout=5.0,
            max_retries=1,
            initial_backoff=0.01,
            max_backoff=0.02,
            circuit_breaker_threshold=5,
            circuit_breaker_recovery=60.0,
        ),
        ProviderConfig(
            name="openai_secondary",
            layer=2,
            base_url="http://openai-secondary.test/v1",
            api_key="sk-test-2",
            model="gpt-3.5-turbo",
            timeout=5.0,
            max_retries=1,
            initial_backoff=0.01,
            max_backoff=0.02,
            circuit_breaker_threshold=5,
            circuit_breaker_recovery=60.0,
        ),
        ProviderConfig(
            name="ollama_local",
            layer=3,
            base_url="http://ollama-local.test/v1",
            api_key="ollama",
            model="llama3",
            timeout=5.0,
            max_retries=1,
            initial_backoff=0.01,
            max_backoff=0.02,
            circuit_breaker_threshold=5,
            circuit_breaker_recovery=60.0,
        ),
    ]


@pytest.mark.asyncio
class TestIncidentSurvivability:
    """
    Prove that incident processing survives total provider failure.
    """

    async def test_classification_survives_all_providers_returning_429(self):
        """
        CRITICAL TEST: When OpenAI returns 429 on ALL providers,
        the deterministic fallback classifier takes over and produces
        a valid classification.
        """
        providers = _make_all_failing_providers()
        chain = ProviderChain(providers)
        fallback = DeterministicFallbackClassifier()
        client = ResilientLLMClient(provider_chain=chain, fallback_classifier=fallback)

        alert_payload = {
            "title": "High database latency with connection pool warnings",
            "summary": (
                "PostgreSQL connection pool exhausted, slow queries detected across all services"
            ),
            "severity": "high",
            "source": "prometheus",
            "labels": {"alertname": "DatabaseLatency", "service": "payment-api"},
        }

        messages = [
            {"role": "system", "content": "Classify this incident."},
            {"role": "user", "content": f"Alert: {alert_payload}"},
        ]

        with respx.mock:
            # ALL providers return 429
            respx.post("http://openai-primary.test/v1/chat/completions").mock(
                return_value=httpx.Response(429, json={"error": {"message": "Rate limit exceeded"}})
            )
            respx.post("http://openai-secondary.test/v1/chat/completions").mock(
                return_value=httpx.Response(429, json={"error": {"message": "Rate limit exceeded"}})
            )
            respx.post("http://ollama-local.test/v1/chat/completions").mock(
                return_value=httpx.Response(429, json={"error": {"message": "Too many requests"}})
            )

            result, chain_result = await client.classify_with_fallback(
                messages,
                alert_payload,
                structured_output_model=RouterOutput,
            )

        # ASSERTIONS: The system MUST produce a valid classification
        assert result is not None, "Classification must not be None"
        assert isinstance(result, FallbackClassification), "Must use deterministic fallback"
        assert result.incident_type == "database", (
            f"Expected 'database', got '{result.incident_type}'"
        )
        assert result.severity == "high"
        assert result.fallback is True
        assert result.provider_used == "deterministic_fallback"
        assert result.confidence > 0.0

        # ASSERTIONS: Transparency metadata must be complete
        assert chain_result.fallback_activated is True
        assert chain_result.provider_used == "deterministic_fallback"
        assert chain_result.layer_used == 4
        assert len(chain_result.attempts) == 3  # All 3 providers were tried

        # ASSERTIONS: Operating mode must reflect the failure
        mode_manager = OperatingModeManager()
        assert mode_manager.current_mode == OperatingMode.SAFE_MODE

    async def test_classification_survives_network_timeout(self):
        """
        When providers timeout (network failure), fallback still works.
        """
        providers = _make_all_failing_providers()
        chain = ProviderChain(providers)
        fallback = DeterministicFallbackClassifier()
        client = ResilientLLMClient(provider_chain=chain, fallback_classifier=fallback)

        alert_payload = {
            "title": "CPU spike on worker nodes",
            "summary": "CPU utilization above 95% across all worker pods",
            "severity": "critical",
        }

        messages = [
            {"role": "system", "content": "Classify this incident."},
            {"role": "user", "content": f"Alert: {alert_payload}"},
        ]

        with respx.mock:
            # ALL providers timeout
            respx.post("http://openai-primary.test/v1/chat/completions").mock(
                side_effect=httpx.ConnectTimeout("Connection timed out")
            )
            respx.post("http://openai-secondary.test/v1/chat/completions").mock(
                side_effect=httpx.ReadTimeout("Read timed out")
            )
            respx.post("http://ollama-local.test/v1/chat/completions").mock(
                side_effect=httpx.ConnectError("Connection refused")
            )

            result, chain_result = await client.classify_with_fallback(
                messages,
                alert_payload,
                structured_output_model=RouterOutput,
            )

        assert result is not None
        assert isinstance(result, FallbackClassification)
        assert result.incident_type == "cpu"
        assert result.severity == "critical"
        assert result.requires_immediate_investigation is True

    async def test_partial_failure_uses_secondary(self):
        """
        When primary fails but secondary succeeds, uses secondary.
        """
        providers = _make_all_failing_providers()
        chain = ProviderChain(providers)
        fallback = DeterministicFallbackClassifier()
        client = ResilientLLMClient(provider_chain=chain, fallback_classifier=fallback)

        alert_payload = {
            "title": "Memory leak detected",
            "summary": "OOM killed containers",
            "severity": "high",
        }

        messages = [
            {"role": "system", "content": "Classify."},
            {"role": "user", "content": "test"},
        ]

        valid_llm_response = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": (
                        '{"incident_type": "memory", "severity": "high", "confidence": 0.85,'
                        ' "requires_immediate_investigation": true,'
                        ' "recommended_workflow": "full_investigation",'
                        ' "rationale": "OOM kill detected"}'
                    )
                }
            }]
        }

        with respx.mock:
            respx.post("http://openai-primary.test/v1/chat/completions").mock(
                return_value=httpx.Response(429, json={"error": "rate limited"})
            )
            respx.post("http://openai-secondary.test/v1/chat/completions").mock(
                return_value=httpx.Response(200, json=valid_llm_response)
            )

            result, chain_result = await client.classify_with_fallback(
                messages,
                alert_payload,
                structured_output_model=RouterOutput,
            )

        assert result is not None
        assert isinstance(result, RouterOutput)
        assert result.incident_type == "memory"
        assert chain_result.provider_used == "openai_secondary"
        assert chain_result.layer_used == 2
        assert chain_result.fallback_activated is True  # Because it's not layer 1

    async def test_failure_transparency_complete(self):
        """
        All failure metadata is recorded for operator visibility.
        """
        providers = _make_all_failing_providers()
        chain = ProviderChain(providers)
        fallback = DeterministicFallbackClassifier()
        client = ResilientLLMClient(provider_chain=chain, fallback_classifier=fallback)

        alert_payload = {"title": "Test", "summary": "Test", "severity": "low"}
        messages = [{"role": "user", "content": "test"}]

        with respx.mock:
            respx.post("http://openai-primary.test/v1/chat/completions").mock(
                return_value=httpx.Response(429, json={"error": "rate limited"})
            )
            respx.post("http://openai-secondary.test/v1/chat/completions").mock(
                return_value=httpx.Response(500, json={"error": "internal error"})
            )
            respx.post("http://ollama-local.test/v1/chat/completions").mock(
                side_effect=httpx.ConnectError("Connection refused")
            )

            result, chain_result = await client.classify_with_fallback(
                messages,
                alert_payload,
                structured_output_model=RouterOutput,
            )

        # Verify full transparency
        result_dict = chain_result.to_dict()
        assert result_dict["provider_used"] == "deterministic_fallback"
        assert result_dict["layer_used"] == 4
        assert result_dict["fallback_activated"] is True
        assert result_dict["attempt_count"] == 3
        assert result_dict["operating_mode"] == "SAFE_MODE"

        # Each attempt has error details
        for attempt in result_dict["attempts"]:
            assert "error" in attempt
            assert attempt["error"] is not None
            valid_providers = ("openai_primary", "openai_secondary", "ollama_local")
            assert attempt["provider_name"] in valid_providers
