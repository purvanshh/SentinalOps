import asyncio
import time

from core.config import get_settings
from redis.asyncio import Redis


class RedisStateManager:
    def __init__(self, redis_client: Redis | None = None) -> None:
        settings = get_settings()
        self.redis = redis_client or Redis.from_url(settings.redis_url, decode_responses=True)

    async def get_lock(
        self,
        lock_name: str,
        acquire_timeout: float = 10.0,
        lock_timeout: float = 30.0,
    ) -> str | None:
        identifier = str(time.time())
        end = time.time() + acquire_timeout
        while time.time() < end:
            if await self.redis.set(f"lock:{lock_name}", identifier, ex=int(lock_timeout), nx=True):
                return identifier
            await asyncio.sleep(0.1)
        return None

    async def release_lock(self, lock_name: str, identifier: str) -> bool:
        lua_release = """
        if redis.call('get', KEYS[1]) == ARGV[1] then
            return redis.call('del', KEYS[1])
        else
            return 0
        end
        """
        result = await self.redis.eval(lua_release, 1, f"lock:{lock_name}", identifier)
        return bool(result)
