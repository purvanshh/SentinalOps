from typing import Any

import httpx

from core.config import get_settings


class LokiClient:
    def __init__(
        self,
        base_url: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.loki_url).rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=15.0, transport=transport)

    async def close(self) -> None:
        await self._client.aclose()

    async def query_range(self, logql: str, start: str, end: str) -> dict[str, Any]:
        response = await self._client.get(
            "/loki/api/v1/query_range",
            params={"query": logql, "start": start, "end": end},
        )
        response.raise_for_status()
        return response.json()
