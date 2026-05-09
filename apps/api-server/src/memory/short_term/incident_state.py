import json
from typing import Any

from redis.asyncio import Redis

from core.config import get_settings


class IncidentStateStore:
    def __init__(self, redis_client: Redis | None = None, ttl_seconds: int = 3600) -> None:
        settings = get_settings()
        self.redis = redis_client or Redis.from_url(settings.redis_url, decode_responses=True)
        self.ttl_seconds = ttl_seconds

    def _key(self, incident_id: str) -> str:
        return f"incident-state:{incident_id}"

    async def save_state(self, incident_id: str, state_dict: dict[str, Any]) -> None:
        await self.redis.set(self._key(incident_id), json.dumps(state_dict), ex=self.ttl_seconds)

    async def load_state(self, incident_id: str) -> dict[str, Any] | None:
        payload = await self.redis.get(self._key(incident_id))
        if payload is None:
            return None
        return json.loads(payload)

    async def delete_state(self, incident_id: str) -> None:
        await self.redis.delete(self._key(incident_id))
