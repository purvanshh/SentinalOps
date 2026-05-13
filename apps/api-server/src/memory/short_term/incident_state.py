import json
from typing import Any

import structlog
from core.config import get_settings
from redis.asyncio import Redis

logger = structlog.get_logger(__name__)


class IncidentStateStore:
    def __init__(self, redis_client: Redis | None = None, ttl_seconds: int = 3600) -> None:
        settings = get_settings()
        self.redis = redis_client or Redis.from_url(settings.redis_url, decode_responses=True)
        self.ttl_seconds = ttl_seconds

    def _key(self, incident_id: str) -> str:
        return f"incident-state:{incident_id}"

    async def save_state(self, incident_id: str, state_dict: dict[str, Any]) -> bool:
        """Persist incident state to Redis.

        Returns True on success, False when Redis is unavailable. Callers
        must not treat a False return as fatal — the system continues in
        degraded mode without the short-term state cache.
        """
        try:
            await self.redis.set(
                self._key(incident_id), json.dumps(state_dict), ex=self.ttl_seconds
            )
            return True
        except Exception as exc:
            logger.warning(
                "incident_state_save_failed",
                incident_id=incident_id,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return False

    async def load_state(self, incident_id: str) -> dict[str, Any] | None:
        """Load incident state from Redis.

        Returns None when Redis is unavailable or the key is not found.
        Callers should treat None as 'state not available' and proceed
        without the cache (the graph reconstructs state from PostgreSQL).
        """
        try:
            payload = await self.redis.get(self._key(incident_id))
            if payload is None:
                return None
            return json.loads(payload)
        except Exception as exc:
            logger.warning(
                "incident_state_load_failed",
                incident_id=incident_id,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return None

    async def delete_state(self, incident_id: str) -> bool:
        """Remove incident state from Redis.

        Returns True on success, False when Redis is unavailable.
        """
        try:
            await self.redis.delete(self._key(incident_id))
            return True
        except Exception as exc:
            logger.warning(
                "incident_state_delete_failed",
                incident_id=incident_id,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return False
