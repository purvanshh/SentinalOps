from __future__ import annotations

import importlib
import sys

import pytest
from core.llm_client import LLMClient, LLMClientError
from core.runtime_context import disallow_live_providers
from evaluation.benchmark_suite import load_benchmark_suite
from evaluation.orchestration_runner import run_agent_pipeline


def test_importing_db_session_does_not_create_engine(monkeypatch) -> None:
    import sqlalchemy.ext.asyncio as sqlalchemy_asyncio

    sys.modules.pop("db.session", None)
    monkeypatch.setattr(
        sqlalchemy_asyncio,
        "create_async_engine",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("engine created at import")),
    )

    module = importlib.import_module("db.session")

    assert hasattr(module, "get_engine")


def test_importing_evaluation_runner_does_not_build_provider_chain(monkeypatch) -> None:
    import core.resilience.resilient_llm_client as resilient_llm_client

    sys.modules.pop("evaluation.runner", None)
    monkeypatch.setattr(
        resilient_llm_client,
        "build_provider_chain_from_settings",
        lambda: (_ for _ in ()).throw(AssertionError("provider chain built during import")),
    )

    module = importlib.import_module("evaluation.runner")

    assert hasattr(module, "run_evaluation")


def test_live_llm_client_forbidden_in_evaluation_context() -> None:
    with disallow_live_providers():
        with pytest.raises(LLMClientError, match="disabled in evaluation mode"):
            LLMClient()


@pytest.mark.asyncio
async def test_run_agent_pipeline_never_initializes_live_llm_client(monkeypatch) -> None:
    benchmark = load_benchmark_suite().incidents[0]
    original_init = LLMClient.__init__

    def fail_init(self, *args, **kwargs):
        raise AssertionError("live llm client initialized during evaluation")

    monkeypatch.setattr(LLMClient, "__init__", fail_init)
    try:
        outputs = await run_agent_pipeline(benchmark)
    finally:
        monkeypatch.setattr(LLMClient, "__init__", original_init)

    assert outputs.execution_id.startswith("eval-")


@pytest.mark.asyncio
async def test_run_agent_pipeline_is_deterministic_for_same_benchmark() -> None:
    benchmark = load_benchmark_suite().incidents[0]

    first = await run_agent_pipeline(benchmark)
    second = await run_agent_pipeline(benchmark)

    assert first.execution_id == second.execution_id
    assert first.trace.thread_id == second.trace.thread_id
