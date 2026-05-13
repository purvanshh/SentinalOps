from typing import Any

import httpx
from core.config import get_settings


class PrometheusClient:
    def __init__(
        self,
        base_url: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.prometheus_url).rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=15.0, transport=transport)
        self._cache: dict[tuple[str, str, str, str], dict[str, Any]] = {}

    async def close(self) -> None:
        await self._client.aclose()

    async def query_range(
        self,
        promql: str,
        start: str,
        end: str,
        step: str,
    ) -> dict[str, Any]:
        cache_key = (promql, start, end, step)
        if cache_key in self._cache:
            return self._cache[cache_key]

        response = await self._client.get(
            "/api/v1/query_range",
            params={"query": promql, "start": start, "end": end, "step": step},
        )
        response.raise_for_status()
        payload = response.json()
        self._cache[cache_key] = payload
        return payload
