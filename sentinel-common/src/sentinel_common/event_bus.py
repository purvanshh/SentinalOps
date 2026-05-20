"""Event streaming layer using Redis Streams (Kafka-ready interface)."""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Awaitable

from .events import Event, EventType


EventHandler = Callable[[Event], Awaitable[None]]


@dataclass
class Subscription:
    event_types: list[EventType]
    handler: EventHandler
    group: str = "default"


class EventBus:
    """Unified event bus with pub/sub and streaming support.

    Starts with in-memory dispatch. Swap backend to Redis Streams
    or Kafka by implementing StreamBackend protocol.
    """

    def __init__(self, backend: "StreamBackend | None" = None):
        self._backend = backend or InMemoryBackend()
        self._subscriptions: list[Subscription] = []
        self._handlers: dict[EventType, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_types: list[EventType], handler: EventHandler, group: str = "default") -> None:
        sub = Subscription(event_types=event_types, handler=handler, group=group)
        self._subscriptions.append(sub)
        for et in event_types:
            self._handlers[et].append(handler)

    async def publish(self, event: Event) -> None:
        await self._backend.append(event)
        handlers = self._handlers.get(event.event_type, [])
        await asyncio.gather(*(h(event) for h in handlers), return_exceptions=True)

    async def replay(self, incident_id: str, since: datetime | None = None) -> list[Event]:
        return await self._backend.read(incident_id, since)


class StreamBackend:
    """Protocol for event stream backends."""

    async def append(self, event: Event) -> None:
        raise NotImplementedError

    async def read(self, incident_id: str, since: datetime | None = None) -> list[Event]:
        raise NotImplementedError


class InMemoryBackend(StreamBackend):
    """In-memory backend for development and testing."""

    def __init__(self) -> None:
        self._streams: dict[str, list[Event]] = defaultdict(list)

    async def append(self, event: Event) -> None:
        self._streams[event.incident_id].append(event)

    async def read(self, incident_id: str, since: datetime | None = None) -> list[Event]:
        events = self._streams.get(incident_id, [])
        if since:
            events = [e for e in events if e.timestamp >= since]
        return events


class RedisStreamBackend(StreamBackend):
    """Redis Streams backend for production use."""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self._redis_url = redis_url
        self._client: Any = None

    async def _ensure_client(self) -> Any:
        if self._client is None:
            import redis.asyncio as aioredis
            self._client = aioredis.from_url(self._redis_url)
        return self._client

    async def append(self, event: Event) -> None:
        client = await self._ensure_client()
        stream_key = f"sentinel:events:{event.incident_id}"
        await client.xadd(stream_key, {"data": json.dumps(event.to_dict())})

    async def read(self, incident_id: str, since: datetime | None = None) -> list[Event]:
        client = await self._ensure_client()
        stream_key = f"sentinel:events:{incident_id}"
        start = "0" if since is None else str(int(since.timestamp() * 1000))
        raw = await client.xrange(stream_key, min=start)
        return [Event.from_dict(json.loads(entry[1][b"data"])) for entry in raw]
