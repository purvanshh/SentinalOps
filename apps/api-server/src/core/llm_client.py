import json
from collections.abc import Sequence
from typing import Any

import httpx
from core.config import get_settings
from core.exceptions import SentinelOpsError
from core.runtime_context import live_provider_access_allowed
from memory.short_term.llm_cache import get_cached, set_cached
from pydantic import BaseModel, ValidationError


class LLMClientError(SentinelOpsError):
    """Raised when the LLM client cannot produce a valid response."""


class LLMClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 15.0,
        max_retries: int = 2,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not live_provider_access_allowed() and transport is None:
            raise LLMClientError(
                "Live LLMClient initialization is disabled in evaluation mode. "
                "Inject a mock client."
            )
        settings = get_settings()
        self.base_url = (base_url or settings.resolved_llm_base_url).rstrip("/")
        raw_key = api_key or settings.resolved_llm_api_key
        self.api_key = (
            raw_key.get_secret_value() if hasattr(raw_key, "get_secret_value") else raw_key
        )
        self.model = model or settings.resolved_llm_model
        self.timeout = timeout
        self.max_retries = max_retries
        self._transport = transport
        self._client: httpx.AsyncClient | None = None

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                transport=self._transport,
            )
        return self._client

    async def generate(
        self,
        messages: Sequence[dict[str, Any]],
        *,
        temperature: float = 0.1,
        tools: list[dict[str, Any]] | None = None,
        structured_output_model: type[BaseModel] | None = None,
    ) -> BaseModel | dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": list(messages),
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        cached = get_cached(payload)
        if cached is not None:
            if structured_output_model is None:
                return cached
            return self._parse_structured_output(cached.get("content", ""), structured_output_model)

        last_error: Exception | None = None
        for _attempt in range(self.max_retries + 1):
            try:
                response = await self._get_client().post("/chat/completions", json=payload)
                response.raise_for_status()
                body = response.json()
                message = body["choices"][0]["message"]
                set_cached(payload, message)
                if structured_output_model is None:
                    return message
                content = message.get("content", "")
                return self._parse_structured_output(content, structured_output_model)
            except (httpx.HTTPError, KeyError, ValidationError, json.JSONDecodeError) as exc:
                last_error = exc

        raise LLMClientError(
            f"Unable to generate response after retries: {last_error}"
        ) from last_error

    def _parse_structured_output(
        self,
        content: str | list[dict[str, Any]],
        structured_output_model: type[BaseModel],
    ) -> BaseModel:
        if isinstance(content, list):
            text_content = "".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            ).strip()
        else:
            text_content = content.strip()

        payload = json.loads(text_content)
        return structured_output_model.model_validate(payload)
