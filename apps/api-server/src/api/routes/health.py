import asyncio

import httpx
from fastapi import APIRouter
from redis.asyncio import Redis

from core.config import get_settings
from core.resilience.operating_mode import OperatingModeManager
from core.resilience.resilient_llm_client import get_provider_chain
from observability.metrics import build_metrics_snapshot, observe_api_request

router = APIRouter(tags=["health"])


def _service_status(url: str | None) -> str:
    return "configured" if url else "missing"


async def _probe_redis(url: str) -> str:
    try:
        client = Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1)
        await asyncio.wait_for(client.ping(), timeout=1.0)
        await client.aclose()
        return "reachable"
    except Exception:
        return "unreachable"


async def _probe_qdrant(url: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            response = await client.get(f"{url.rstrip('/')}/healthz")
            return "reachable" if response.is_success else "degraded"
    except Exception:
        return "unreachable"


@router.get("/health")
async def health_check() -> dict[str, object]:
    observe_api_request("GET", "/health")
    settings = get_settings()
    mode_manager = OperatingModeManager()

    redis_status, qdrant_status = await asyncio.gather(
        _probe_redis(settings.redis_url),
        _probe_qdrant(settings.qdrant_url),
    )

    return {
        "status": "ok",
        "environment": settings.app_env,
        "operating_mode": mode_manager.current_mode.value,
        "resilience": mode_manager.to_dict(),
        "services": {
            "postgres": f"{settings.postgres_server}:{settings.postgres_port}",
            "redis": redis_status,
            "qdrant": qdrant_status,
            "prometheus": _service_status(settings.prometheus_url),
            "grafana": _service_status(settings.grafana_url),
            "loki": _service_status(settings.loki_url),
            "tempo": _service_status(settings.tempo_url),
        },
        "provider_chain": get_provider_chain().get_health(),
        "metrics": build_metrics_snapshot(),
    }
