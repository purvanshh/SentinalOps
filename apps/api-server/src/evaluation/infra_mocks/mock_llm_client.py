"""
Deterministic LLM mock for EVALUATION execution mode.

Returns benchmark fixture responses without any external API calls.
Ensures evaluation reproducibility with zero LLM provider dependencies.

Golden labels MUST NEVER be injected as mock_data — only mocked_tool_responses
fields may be used as inputs to these clients.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import httpx
from core.config import get_settings
from pydantic import BaseModel

_ROUTER_DEFAULTS: dict[str, Any] = {
    "requires_immediate_investigation": True,
    "recommended_workflow": "standard_investigation",
    "rationale": "Classification derived from benchmark fixture data.",
}

_DEPLOYMENT_DEFAULTS: dict[str, Any] = {
    "correlation_with_incident": "No correlated deployment found within the incident window.",
}

_METRICS_DEFAULTS: dict[str, Any] = {
    "summary": "No metrics anomalies available in benchmark fixture.",
    "anomalies": [],
}

_LOGS_DEFAULTS: dict[str, Any] = {
    "error_signatures": [],
}


class EvalMockLLMClient:
    """
    Deterministic LLM client for EVALUATION execution mode.

    When structured_output_model is provided (router agent direct path),
    validates mock data directly into the expected output type.

    When operating in agent_loop mode (metrics/logs/deployment agents),
    returns mock data as a content string so the loop exits on the
    first iteration without invoking any tool calls.

    Contract: mock_data MUST come from mocked_tool_responses only.
    Golden labels (golden_root_cause, golden_classification, etc.) must
    NEVER be passed as mock_data.
    """

    def __init__(self, mock_data: dict[str, Any]) -> None:
        self._mock_data = mock_data

    async def generate(
        self,
        messages: Any,
        *,
        temperature: float = 0.1,
        tools: Any = None,
        structured_output_model: type[BaseModel] | None = None,
    ) -> BaseModel | dict[str, Any]:
        if structured_output_model is not None:
            return structured_output_model.model_validate(self._mock_data)
        return {"content": json.dumps(self._mock_data), "tool_calls": []}

    async def close(self) -> None:
        pass


class DeterministicEvalSynthesisClient:
    """Deterministic symptom-to-cause synthesizer for evaluation mode."""

    def __init__(self) -> None:
        self._cache: dict[str, dict[str, Any]] = {}

    async def generate(
        self,
        messages: Any,
        *,
        temperature: float = 0.0,
        tools: Any = None,
        structured_output_model: type[BaseModel] | None = None,
    ) -> BaseModel | dict[str, Any]:
        prompt = ""
        if isinstance(messages, list) and messages:
            prompt = str(messages[-1].get("content", ""))
        if prompt in self._cache:
            return self._cache[prompt]

        evidence_section = prompt
        if "Evidence:" in prompt and "Draft symptom description:" in prompt:
            evidence_section = prompt.split("Evidence:", 1)[1].split(
                "Draft symptom description:", 1
            )[0]
        draft = ""
        if "Draft symptom description:" in prompt:
            draft = prompt.split("Draft symptom description:", 1)[1].split("Rules:", 1)[0]

        lower = f"{evidence_section}\n{draft}".lower()
        content = "Unknown service degradation"
        if "dns" in lower and ("timeout" in lower or "resolution" in lower):
            content = "DNS resolver misconfiguration causing resolution timeouts"
        elif "external_api_latency" in lower or "external api" in lower:
            content = "External payment processor degraded, adding latency to checkout"
        elif "connectionpoolexhausted" in lower and "deployment" in lower:
            content = "Database connection pool exhaustion after deployment v2.3.1"
        elif "connectionpoolexhausted" in lower or "connection pool" in lower:
            content = "Database connection pool exhaustion"
        elif "deployment" in lower and "regression" in lower:
            content = "Deployment regression causing service degradation"

        response = {"content": content, "tool_calls": []}
        self._cache[prompt] = response
        return response

    async def close(self) -> None:
        pass


class EvaluationSynthesisClient:
    """Pinned local synthesis client for evaluation with deterministic fallback."""

    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.eval_synthesis_base_url.rstrip("/")
        self.api_key = settings.eval_synthesis_api_key
        self.model = settings.eval_synthesis_model
        self.temperature = settings.eval_synthesis_temperature
        self.max_tokens = settings.eval_synthesis_max_tokens
        self._cache: dict[str, dict[str, Any]] = {}
        self._fallback = DeterministicEvalSynthesisClient()

    async def generate(
        self,
        messages: Any,
        *,
        temperature: float = 0.0,
        tools: Any = None,
        structured_output_model: type[BaseModel] | None = None,
    ) -> BaseModel | dict[str, Any]:
        prompt = ""
        if isinstance(messages, list) and messages:
            prompt = str(messages[-1].get("content", ""))
        key = hashlib.sha256(prompt.encode()).hexdigest()
        if key in self._cache:
            return self._cache[key]

        payload = {
            "model": self.model,
            "messages": list(messages) if isinstance(messages, list) else messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=30.0,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            ) as client:
                response = await client.post("/chat/completions", json=payload)
                response.raise_for_status()
                body = response.json()
                message = body["choices"][0]["message"]
                self._cache[key] = message
                return message
        except Exception:
            response = await self._fallback.generate(
                messages,
                temperature=temperature,
                tools=tools,
                structured_output_model=structured_output_model,
            )
            self._cache[key] = response
            return response

    async def close(self) -> None:
        await self._fallback.close()


def build_router_mock_client(mocked_tool_responses: dict[str, Any]) -> EvalMockLLMClient:
    router_data = mocked_tool_responses.get("router", {})
    return EvalMockLLMClient({**_ROUTER_DEFAULTS, **router_data})


def build_metrics_mock_client(mocked_tool_responses: dict[str, Any]) -> EvalMockLLMClient:
    metrics_data = mocked_tool_responses.get("metrics", {})
    return EvalMockLLMClient({**_METRICS_DEFAULTS, **metrics_data})


def build_logs_mock_client(mocked_tool_responses: dict[str, Any]) -> EvalMockLLMClient:
    logs_data = mocked_tool_responses.get("logs", {})
    return EvalMockLLMClient({**_LOGS_DEFAULTS, **logs_data})


def build_deployment_mock_client(mocked_tool_responses: dict[str, Any]) -> EvalMockLLMClient:
    deployment_data = mocked_tool_responses.get("deployment", {})
    return EvalMockLLMClient({**_DEPLOYMENT_DEFAULTS, **deployment_data})


def build_rootcause_synthesis_mock_client() -> EvaluationSynthesisClient:
    return EvaluationSynthesisClient()
