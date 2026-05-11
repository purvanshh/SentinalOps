from fastapi import APIRouter

from core.config import get_settings
from core.resilience.operating_mode import OperatingModeManager
from core.resilience.resilient_llm_client import get_provider_chain
from observability.metrics import build_metrics_snapshot, observe_api_request

router = APIRouter(tags=["health"])


def _service_status(url: str | None) -> str:
    return "configured" if url else "missing"


@router.get("/health")
async def health_check() -> dict[str, object]:
    observe_api_request("GET", "/health")
    settings = get_settings()
    mode_manager = OperatingModeManager()

    return {
        "status": "ok",
        "environment": settings.app_env,
        "operating_mode": mode_manager.current_mode.value,
        "resilience": mode_manager.to_dict(),
        "services": {
            "postgres": f"{settings.postgres_server}:{settings.postgres_port}",
            "redis": _service_status(settings.redis_url),
            "qdrant": _service_status(settings.qdrant_url),
            "prometheus": _service_status(settings.prometheus_url),
            "grafana": _service_status(settings.grafana_url),
            "loki": _service_status(settings.loki_url),
            "tempo": _service_status(settings.tempo_url),
        },
        "provider_chain": get_provider_chain().get_health(),
        "metrics": build_metrics_snapshot(),
    }
