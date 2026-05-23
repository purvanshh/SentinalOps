"""
Tests for the multi-layer provider fallback chain.

Verifies that:
- Provider chain tries providers in order
- Circuit breakers prevent calls to failing providers
- Fallback activates when all providers are exhausted
- Operating mode transitions correctly on failures
"""

import httpx
import pytest
import respx
from core.resilience.operating_mode import OperatingMode, OperatingModeManager
from core.resilience.provider_chain import ProviderChain, ProviderConfig


@pytest.fixture(autouse=True)
def reset_mode_manager():
    manager = OperatingModeManager()
    manager.reset()
    yield
    manager.reset()


def _make_providers() -> list[ProviderConfig]:
    return [
        ProviderConfig(
            name="primary",
            layer=1,
            base_url="http://primary.test/v1",
            api_key="key1",
            model="gpt-4",
            timeout=5.0,
            max_retries=1,
            initial_backoff=0.01,
            max_backoff=0.05,
            circuit_breaker_threshold=2,
            circuit_breaker_recovery=0.1,
        ),
        ProviderConfig(
            name="secondary",
            layer=2,
            base_url="http://secondary.test/v1",
            api_key="key2",
            model="gpt-3.5",
            timeout=5.0,
            max_retries=1,
            initial_backoff=0.01,
            max_backoff=0.05,
            circuit_breaker_threshold=2,
            circuit_breaker_recovery=0.1,
        ),
        ProviderConfig(
            name="local",
            layer=3,
            base_url="http://local.test/v1",
            api_key="ollama",
            model="llama3",
            timeout=5.0,
            max_retries=1,
            initial_backoff=0.01,
            max_backoff=0.05,
            circuit_breaker_threshold=2,
            circuit_breaker_recovery=0.1,
        ),
    ]


def _success_response():
    return httpx.Response(
        200,
        json={"choices": [{"message": {"role": "assistant", "content": "test response"}}]},
    )


def _rate_limit_response():
    return httpx.Response(429, json={"error": "rate limited"})


def _server_error_response():
    return httpx.Response(500, json={"error": "internal error"})


@pytest.mark.asyncio
class TestProviderChain:
    async def test_primary_success(self):
        """Primary provider succeeds on first try."""
        chain = ProviderChain(_make_providers())
        messages = [{"role": "user", "content": "test"}]

        with respx.mock:
            respx.post("http://primary.test/v1/chat/completions").mock(
                return_value=_success_response()
            )

            result = await chain.generate(messages)
            assert result.response is not None
            assert result.provider_used == "primary"
            assert result.layer_used == 1
            assert result.fallback_activated is False

    async def test_fallback_to_secondary_on_429(self):
        """Primary returns 429, falls back to secondary."""
        chain = ProviderChain(_make_providers())
        messages = [{"role": "user", "content": "test"}]

        with respx.mock:
            primary_route = respx.post("http://primary.test/v1/chat/completions").mock(
                return_value=_rate_limit_response()
            )
            respx.post("http://secondary.test/v1/chat/completions").mock(
                return_value=_success_response()
            )

            result = await chain.generate(messages)
            assert result.response is not None
            assert result.provider_used == "secondary"
            assert result.layer_used == 2
            assert result.fallback_activated is True
            assert primary_route.call_count == 1

    async def test_auth_failure_trips_circuit_without_retry(self):
        """401/403 failures should fast-fail and open the circuit immediately."""
        chain = ProviderChain(_make_providers())
        messages = [{"role": "user", "content": "test"}]

        with respx.mock:
            primary_route = respx.post("http://primary.test/v1/chat/completions").mock(
                return_value=httpx.Response(401, json={"error": "unauthorized"})
            )
            respx.post("http://secondary.test/v1/chat/completions").mock(
                return_value=_success_response()
            )

            result = await chain.generate(messages)

        assert result.provider_used == "secondary"
        assert primary_route.call_count == 1
        assert chain._circuit_breakers["primary"].state.value == "OPEN"

    async def test_fallback_to_local_when_primary_and_secondary_fail(self):
        """Both primary and secondary fail, falls back to local."""
        chain = ProviderChain(_make_providers())
        messages = [{"role": "user", "content": "test"}]

        with respx.mock:
            respx.post("http://primary.test/v1/chat/completions").mock(
                return_value=_rate_limit_response()
            )
            respx.post("http://secondary.test/v1/chat/completions").mock(
                return_value=_server_error_response()
            )
            respx.post("http://local.test/v1/chat/completions").mock(
                return_value=_success_response()
            )

            result = await chain.generate(messages)
            assert result.response is not None
            assert result.provider_used == "local"
            assert result.layer_used == 3

    async def test_all_providers_exhausted(self):
        """All providers fail, returns None response."""
        chain = ProviderChain(_make_providers())
        messages = [{"role": "user", "content": "test"}]

        with respx.mock:
            respx.post("http://primary.test/v1/chat/completions").mock(
                return_value=_rate_limit_response()
            )
            respx.post("http://secondary.test/v1/chat/completions").mock(
                return_value=_server_error_response()
            )
            respx.post("http://local.test/v1/chat/completions").mock(
                return_value=_server_error_response()
            )

            result = await chain.generate(messages)
            assert result.response is None
            assert result.provider_used == "none"
            assert result.fallback_activated is True
            assert len(result.attempts) == 3

    async def test_operating_mode_transitions_on_failure(self):
        """Operating mode transitions as providers fail."""
        chain = ProviderChain(_make_providers())
        messages = [{"role": "user", "content": "test"}]
        mode_manager = OperatingModeManager()

        assert mode_manager.current_mode == OperatingMode.FULL

        with respx.mock:
            respx.post("http://primary.test/v1/chat/completions").mock(
                return_value=_rate_limit_response()
            )
            respx.post("http://secondary.test/v1/chat/completions").mock(
                return_value=_rate_limit_response()
            )
            respx.post("http://local.test/v1/chat/completions").mock(
                return_value=_rate_limit_response()
            )

            result = await chain.generate(messages)
            assert result.response is None
            # Mode should have transitioned through DEGRADED → LOCAL_ONLY → SAFE_MODE
            assert mode_manager.current_mode == OperatingMode.SAFE_MODE

    async def test_circuit_breaker_skips_open_provider(self):
        """Circuit breaker prevents calls to a known-failing provider."""
        chain = ProviderChain(_make_providers())
        messages = [{"role": "user", "content": "test"}]

        # Force the primary circuit breaker open
        chain._circuit_breakers["primary"].force_open()

        with respx.mock:
            # Primary should NOT be called
            primary_route = respx.post("http://primary.test/v1/chat/completions").mock(
                return_value=_success_response()
            )
            respx.post("http://secondary.test/v1/chat/completions").mock(
                return_value=_success_response()
            )

            result = await chain.generate(messages)
            assert result.provider_used == "secondary"
            assert primary_route.call_count == 0

    async def test_attempts_recorded_for_transparency(self):
        """All attempts are recorded for failure transparency."""
        chain = ProviderChain(_make_providers())
        messages = [{"role": "user", "content": "test"}]

        with respx.mock:
            respx.post("http://primary.test/v1/chat/completions").mock(
                return_value=_rate_limit_response()
            )
            respx.post("http://secondary.test/v1/chat/completions").mock(
                return_value=_success_response()
            )

            result = await chain.generate(messages)
            assert len(result.attempts) == 2
            assert result.attempts[0].provider_name == "primary"
            assert result.attempts[0].success is False
            assert result.attempts[1].provider_name == "secondary"
            assert result.attempts[1].success is True

    async def test_get_health(self):
        """Health endpoint returns provider status."""
        chain = ProviderChain(_make_providers())
        health = chain.get_health()
        assert "operating_mode" in health
        assert "providers" in health
        assert "primary" in health["providers"]
        assert health["providers"]["primary"]["state"] == "CLOSED"

    async def test_result_includes_provider_health_snapshot(self):
        chain = ProviderChain(_make_providers())
        messages = [{"role": "user", "content": "test"}]

        with respx.mock:
            respx.post("http://primary.test/v1/chat/completions").mock(
                return_value=_success_response()
            )

            result = await chain.generate(messages)

        assert "providers" in result.provider_health
        assert "primary" in result.provider_health["providers"]
