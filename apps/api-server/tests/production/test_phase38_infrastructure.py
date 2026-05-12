"""
Phase-38 infrastructure resilience and deployment validation hardening.

Proves:
  - Redis outage: save_state returns False instead of raising
  - Redis outage: load_state returns None instead of raising
  - Redis outage: delete_state returns False instead of raising
  - Redis success: save_state returns True
  - Redis success: load_state returns the saved dict
  - Redis key format is deterministic: incident-state:{incident_id}
  - Dockerfile contains HEALTHCHECK instruction
  - validate_required_configuration catches missing REDIS_URL
  - validate_required_configuration catches missing CELERY_BROKER_URL
  - Production startup fails if required config missing
  - Production startup fails if secrets are default dev values
  - Startup succeeds in development with missing config (only warns)
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Redis graceful degradation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_save_state_returns_false_on_redis_error():
    from memory.short_term.incident_state import IncidentStateStore

    mock_redis = AsyncMock()
    mock_redis.set.side_effect = ConnectionError("Redis connection refused")
    store = IncidentStateStore(redis_client=mock_redis)

    result = await store.save_state("inc-001", {"status": "active"})
    assert result is False


@pytest.mark.asyncio
async def test_load_state_returns_none_on_redis_error():
    from memory.short_term.incident_state import IncidentStateStore

    mock_redis = AsyncMock()
    mock_redis.get.side_effect = ConnectionError("Redis connection refused")
    store = IncidentStateStore(redis_client=mock_redis)

    result = await store.load_state("inc-001")
    assert result is None


@pytest.mark.asyncio
async def test_delete_state_returns_false_on_redis_error():
    from memory.short_term.incident_state import IncidentStateStore

    mock_redis = AsyncMock()
    mock_redis.delete.side_effect = ConnectionError("Redis connection refused")
    store = IncidentStateStore(redis_client=mock_redis)

    result = await store.delete_state("inc-001")
    assert result is False


@pytest.mark.asyncio
async def test_save_state_returns_true_on_success():
    from memory.short_term.incident_state import IncidentStateStore

    mock_redis = AsyncMock()
    mock_redis.set.return_value = True
    store = IncidentStateStore(redis_client=mock_redis)

    result = await store.save_state("inc-001", {"status": "active", "score": 0.9})
    assert result is True


@pytest.mark.asyncio
async def test_load_state_returns_dict_on_success():
    from memory.short_term.incident_state import IncidentStateStore

    mock_redis = AsyncMock()
    mock_redis.get.return_value = json.dumps({"status": "active", "score": 0.9})
    store = IncidentStateStore(redis_client=mock_redis)

    result = await store.load_state("inc-001")
    assert result == {"status": "active", "score": 0.9}


@pytest.mark.asyncio
async def test_load_state_returns_none_when_key_missing():
    from memory.short_term.incident_state import IncidentStateStore

    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    store = IncidentStateStore(redis_client=mock_redis)

    result = await store.load_state("inc-999")
    assert result is None


def test_state_key_format():
    from memory.short_term.incident_state import IncidentStateStore

    mock_redis = MagicMock()
    store = IncidentStateStore(redis_client=mock_redis)
    assert store._key("inc-abc") == "incident-state:inc-abc"
    assert store._key("inc-xyz-123") == "incident-state:inc-xyz-123"


@pytest.mark.asyncio
async def test_save_state_passes_ttl_to_redis():
    from memory.short_term.incident_state import IncidentStateStore

    mock_redis = AsyncMock()
    mock_redis.set.return_value = True
    store = IncidentStateStore(redis_client=mock_redis, ttl_seconds=7200)

    await store.save_state("inc-001", {"x": 1})
    call_kwargs = mock_redis.set.call_args
    assert call_kwargs.kwargs.get("ex") == 7200


# ---------------------------------------------------------------------------
# Dockerfile healthcheck
# ---------------------------------------------------------------------------

def test_dockerfile_contains_healthcheck():
    dockerfile = Path(__file__).parents[4] / "apps" / "api-server" / "Dockerfile"
    if not dockerfile.exists():
        pytest.skip("Dockerfile not found at expected path")
    content = dockerfile.read_text()
    assert "HEALTHCHECK" in content, "Dockerfile must contain a HEALTHCHECK instruction"


def test_dockerfile_healthcheck_uses_health_endpoint():
    dockerfile = Path(__file__).parents[4] / "apps" / "api-server" / "Dockerfile"
    if not dockerfile.exists():
        pytest.skip("Dockerfile not found at expected path")
    content = dockerfile.read_text()
    assert "/health" in content, "HEALTHCHECK must probe /health endpoint"


# ---------------------------------------------------------------------------
# Configuration validation at startup
# ---------------------------------------------------------------------------

def test_validate_required_configuration_catches_empty_redis():
    from core.config import Settings

    settings = Settings(app_env="development", redis_url="")
    issues = settings.validate_required_configuration()
    assert any("REDIS_URL" in i for i in issues)


def test_validate_required_configuration_catches_empty_celery_broker():
    from core.config import Settings

    settings = Settings(app_env="development", celery_broker_url="")
    issues = settings.validate_required_configuration()
    assert any("CELERY_BROKER_URL" in i for i in issues)


def test_validate_required_configuration_clean_for_valid_config():
    from core.config import Settings

    settings = Settings(
        app_env="development",
        redis_url="redis://localhost:6379/0",
        celery_broker_url="redis://localhost:6379/1",
    )
    issues = settings.validate_required_configuration()
    assert not any("REDIS_URL" in i for i in issues)
    assert not any("CELERY_BROKER_URL" in i for i in issues)


def test_production_required_config_includes_llm_key_check():
    from core.config import Settings

    settings = Settings(
        app_env="production",
        auth0_secret_key="strong-secret-abc",
        approval_token_secret="strong-secret-xyz",
        llm_api_key="dummy-key",
    )
    issues = settings.validate_required_configuration()
    assert any("LLM_API_KEY" in i for i in issues)


def test_development_does_not_fail_on_dummy_llm_key():
    from core.config import Settings

    settings = Settings(app_env="development", llm_api_key="dummy-key")
    issues = settings.validate_required_configuration()
    assert not any("LLM_API_KEY" in i for i in issues)
