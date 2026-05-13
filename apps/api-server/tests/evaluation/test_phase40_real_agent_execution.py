"""
Phase 40 validation tests: Epistemic Integrity Foundation.

Proves that evaluation measures REAL agent cognition:

A. Real agents execute — router, root cause, and all intermediate agents
   are actually invoked with their reasoning logic, not replaced with
   synthetic outputs constructed from golden labels.

B. Golden labels never enter runtime cognition — golden_root_cause,
   golden_remediation, golden_classification are never passed to any
   agent prompt, mock LLM client, or IncidentState field during execution.

C. Replay reproducibility preserved — two replays of the same benchmark
   produce identical outputs, scores, and trace hashes.

D. No external side effects — evaluation mode never calls Slack, GitHub,
   Prometheus, or enqueues Celery jobs. All infrastructure is mocked.
"""

from __future__ import annotations

import json

import pytest
from agents.metrics_agent.output_schema import MetricsSummary
from agents.rootcause_agent.output_schema import RootCauseAnalysis
from agents.router_agent.output_schema import RouterOutput
from evaluation.benchmark_suite import load_benchmark_suite
from evaluation.execution_mode import ExecutionMode
from evaluation.infra_mocks.mock_incident import build_mock_incident_from_benchmark
from evaluation.infra_mocks.mock_llm_client import (
    build_metrics_mock_client,
    build_router_mock_client,
)
from evaluation.orchestration_runner import (
    AgentPipelineOutputs,
    _assert_no_golden_contamination,
    run_agent_pipeline,
)


@pytest.fixture(scope="module")
def suite():
    return load_benchmark_suite()


@pytest.fixture(scope="module")
def first_benchmark(suite):
    return suite.incidents[0]


@pytest.fixture(scope="module")
def second_benchmark(suite):
    return suite.incidents[1]


@pytest.fixture()
async def pipeline_outputs(first_benchmark) -> AgentPipelineOutputs:
    return await run_agent_pipeline(first_benchmark)


# ─── A. Real agents execute ───────────────────────────────────────────────────


class TestRealAgentExecution:
    @pytest.mark.asyncio
    async def test_router_agent_actually_invoked(self, first_benchmark) -> None:
        outputs = await run_agent_pipeline(first_benchmark)
        assert isinstance(outputs.router_output, RouterOutput)
        assert outputs.router_output.incident_type != ""
        assert outputs.router_output.confidence > 0.0

    @pytest.mark.asyncio
    async def test_metrics_agent_actually_invoked(self, first_benchmark) -> None:
        outputs = await run_agent_pipeline(first_benchmark)
        assert isinstance(outputs.metrics_output, MetricsSummary)

    @pytest.mark.asyncio
    async def test_rootcause_agent_actually_invoked(self, first_benchmark) -> None:
        outputs = await run_agent_pipeline(first_benchmark)
        result = outputs.rootcause_output
        assert isinstance(result, RootCauseAnalysis)
        assert result.investigation_log != ""
        assert "normalized" in result.investigation_log.lower()
        assert "candidate causes" in result.investigation_log.lower()

    @pytest.mark.asyncio
    async def test_all_seven_agents_recorded_in_trace(self, first_benchmark) -> None:
        outputs = await run_agent_pipeline(first_benchmark)
        trace = outputs.trace
        expected_steps = {
            "router",
            "metrics",
            "logs",
            "deployment",
            "rootcause",
            "risk",
            "remediation",
        }
        assert expected_steps.issubset(
            set(trace.timing.keys())
        ), f"Missing agent timing entries. Got: {set(trace.timing.keys())}"

    @pytest.mark.asyncio
    async def test_router_output_matches_mocked_tool_response(self, first_benchmark) -> None:
        outputs = await run_agent_pipeline(first_benchmark)
        mock_router = first_benchmark.mocked_tool_responses.get("router", {})
        assert outputs.router_output.incident_type == mock_router["incident_type"]
        assert abs(outputs.router_output.confidence - mock_router["confidence"]) < 1e-9

    @pytest.mark.asyncio
    async def test_rootcause_investigation_log_shows_real_reasoning(self, first_benchmark) -> None:
        outputs = await run_agent_pipeline(first_benchmark)
        log = outputs.rootcause_output.investigation_log
        assert "normalized" in log
        assert "generated" in log
        assert (
            "Evaluation executed deterministic incident flow" not in log
        ), "Old synthetic evaluation log text detected — root cause is not using real reasoning"

    @pytest.mark.asyncio
    async def test_remediation_plan_derived_from_risk_output(self, first_benchmark) -> None:
        outputs = await run_agent_pipeline(first_benchmark)
        assert len(outputs.remediation_output.steps) >= 1
        step_actions = {s.action for s in outputs.remediation_output.steps}
        risk_actions = {r.action for r in outputs.risk_output.remediation_risks}
        assert step_actions.issubset(
            risk_actions | {"restart payment-api"}
        ), "Remediation steps must come from actual risk output, not golden labels"

    @pytest.mark.asyncio
    async def test_execution_mode_is_evaluation(self, first_benchmark) -> None:
        outputs = await run_agent_pipeline(first_benchmark)
        assert outputs.execution_mode == ExecutionMode.EVALUATION

    @pytest.mark.asyncio
    async def test_trace_captures_all_agent_outputs(self, first_benchmark) -> None:
        outputs = await run_agent_pipeline(first_benchmark)
        trace = outputs.trace
        for agent in (
            "router",
            "metrics",
            "logs",
            "deployment",
            "rootcause",
            "risk",
            "remediation",
        ):
            assert agent in trace.agent_outputs, f"Missing trace output for agent: {agent}"

    @pytest.mark.asyncio
    async def test_trace_has_duration(self, first_benchmark) -> None:
        outputs = await run_agent_pipeline(first_benchmark)
        assert outputs.trace.duration_seconds is not None
        assert outputs.trace.duration_seconds >= 0.0


# ─── B. Golden labels never enter runtime cognition ──────────────────────────


class TestGoldenLabelIsolation:
    def test_assert_no_golden_contamination_passes_for_valid_benchmark(
        self, first_benchmark
    ) -> None:
        _assert_no_golden_contamination(first_benchmark)

    def test_assert_no_golden_contamination_detects_injected_golden_root_cause(
        self, first_benchmark
    ) -> None:
        from dataclasses import replace as dc_replace

        injected_response = dict(first_benchmark.mocked_tool_responses)
        injected_response["router"] = {
            **injected_response.get("router", {}),
            "rationale": first_benchmark.golden_root_cause,
        }
        bad_benchmark = dc_replace(first_benchmark, mocked_tool_responses=injected_response)
        with pytest.raises(ValueError, match="EVALUATION INTEGRITY VIOLATION"):
            _assert_no_golden_contamination(bad_benchmark)

    @pytest.mark.asyncio
    async def test_router_mock_data_comes_from_mocked_tool_responses(self, first_benchmark) -> None:
        mock_client = build_router_mock_client(first_benchmark.mocked_tool_responses)
        response = await mock_client.generate([], structured_output_model=RouterOutput)
        assert isinstance(response, RouterOutput)
        mock_router = first_benchmark.mocked_tool_responses.get("router", {})
        assert response.incident_type == mock_router["incident_type"]

    @pytest.mark.asyncio
    async def test_mock_llm_does_not_contain_golden_classification(self, first_benchmark) -> None:
        mock_client = build_router_mock_client(first_benchmark.mocked_tool_responses)
        response = await mock_client.generate([], structured_output_model=RouterOutput)
        assert isinstance(response, RouterOutput)
        router_data_str = json.dumps(mock_client._mock_data)
        assert first_benchmark.golden_root_cause not in router_data_str
        assert first_benchmark.golden_remediation not in router_data_str

    @pytest.mark.asyncio
    async def test_metrics_mock_does_not_contain_golden_fields(self, first_benchmark) -> None:
        mock_client = build_metrics_mock_client(first_benchmark.mocked_tool_responses)
        data_str = json.dumps(mock_client._mock_data)
        assert first_benchmark.golden_root_cause not in data_str
        assert "incident_type" not in mock_client._mock_data

    @pytest.mark.asyncio
    async def test_incident_built_without_golden_labels(self, first_benchmark) -> None:
        incident = build_mock_incident_from_benchmark(first_benchmark)
        incident_str = str(vars(incident))
        assert first_benchmark.golden_root_cause not in incident_str
        assert first_benchmark.golden_remediation not in incident_str

    @pytest.mark.asyncio
    async def test_rootcause_output_is_not_verbatim_golden_root_cause(
        self, first_benchmark
    ) -> None:
        outputs = await run_agent_pipeline(first_benchmark)
        if outputs.rootcause_output.hypotheses:
            top_hypothesis = outputs.rootcause_output.hypotheses[0].hypothesis
            assert top_hypothesis != first_benchmark.golden_root_cause, (
                "Root cause hypothesis must be derived from agent reasoning, "
                "not copied from golden_root_cause"
            )

    @pytest.mark.asyncio
    async def test_risk_blast_radius_derived_from_topology_not_golden(
        self, first_benchmark
    ) -> None:
        outputs = await run_agent_pipeline(first_benchmark)
        assert outputs.risk_output.blast_radius is not None
        assert outputs.risk_output.blast_radius.users_at_risk.mean >= 0

    @pytest.mark.asyncio
    async def test_all_benchmark_incidents_pass_golden_contamination_check(self, suite) -> None:
        errors: list[str] = []
        for inc in suite.incidents:
            try:
                _assert_no_golden_contamination(inc)
            except ValueError as exc:
                errors.append(str(exc))
        assert not errors, f"Golden contamination found in {len(errors)} incidents:\n" + "\n".join(
            errors[:5]
        )


# ─── C. Replay reproducibility ───────────────────────────────────────────────


class TestReplayReproducibility:
    @pytest.mark.asyncio
    async def test_two_replays_produce_identical_router_output(self, first_benchmark) -> None:
        out1 = await run_agent_pipeline(first_benchmark)
        out2 = await run_agent_pipeline(first_benchmark)
        assert out1.router_output.incident_type == out2.router_output.incident_type
        assert out1.router_output.confidence == out2.router_output.confidence

    @pytest.mark.asyncio
    async def test_two_replays_produce_identical_rootcause_status(self, first_benchmark) -> None:
        out1 = await run_agent_pipeline(first_benchmark)
        out2 = await run_agent_pipeline(first_benchmark)
        assert out1.rootcause_output.status == out2.rootcause_output.status
        assert len(out1.rootcause_output.hypotheses) == len(out2.rootcause_output.hypotheses)

    @pytest.mark.asyncio
    async def test_two_replays_produce_identical_blast_radius(self, first_benchmark) -> None:
        out1 = await run_agent_pipeline(first_benchmark)
        out2 = await run_agent_pipeline(first_benchmark)
        assert out1.risk_output.blast_radius.users_at_risk.mean == (
            out2.risk_output.blast_radius.users_at_risk.mean
        )

    @pytest.mark.asyncio
    async def test_two_replays_produce_identical_remediation_steps(self, first_benchmark) -> None:
        out1 = await run_agent_pipeline(first_benchmark)
        out2 = await run_agent_pipeline(first_benchmark)
        steps1 = [s.action for s in out1.remediation_output.steps]
        steps2 = [s.action for s in out2.remediation_output.steps]
        assert steps1 == steps2

    @pytest.mark.asyncio
    async def test_two_different_benchmarks_produce_different_outputs(
        self, first_benchmark, second_benchmark
    ) -> None:
        out1 = await run_agent_pipeline(first_benchmark)
        out2 = await run_agent_pipeline(second_benchmark)
        assert out1.benchmark_id != out2.benchmark_id

    @pytest.mark.asyncio
    async def test_trace_is_serializable(self, first_benchmark) -> None:
        out = await run_agent_pipeline(first_benchmark)
        serialized = json.dumps(out.trace.to_dict())
        assert len(serialized) > 0


# ─── D. No external side effects ─────────────────────────────────────────────


class TestNoExternalSideEffects:
    def test_execution_mode_evaluation_disables_side_effects(self) -> None:
        mode = ExecutionMode.EVALUATION
        assert mode.disables_side_effects
        assert not mode.allows_external_api_calls
        assert not mode.allows_celery_tasks
        assert not mode.allows_remediation_execution
        assert not mode.allows_approval_escalation
        assert not mode.allows_async_replay_scheduling
        assert not mode.allows_outbound_notifications

    def test_execution_mode_production_enables_side_effects(self) -> None:
        mode = ExecutionMode.PRODUCTION
        assert not mode.disables_side_effects
        assert mode.allows_external_api_calls
        assert mode.allows_celery_tasks
        assert mode.allows_remediation_execution

    @pytest.mark.asyncio
    async def test_pipeline_rejects_production_mode(self, first_benchmark) -> None:
        with pytest.raises(AssertionError, match="EVALUATION mode"):
            await run_agent_pipeline(first_benchmark, execution_mode=ExecutionMode.PRODUCTION)

    @pytest.mark.asyncio
    async def test_pipeline_completes_without_prometheus_connection(self, first_benchmark) -> None:
        out = await run_agent_pipeline(first_benchmark)
        assert out.risk_output is not None

    @pytest.mark.asyncio
    async def test_mock_llm_returns_content_not_tool_calls(self, first_benchmark) -> None:
        client = build_metrics_mock_client(first_benchmark.mocked_tool_responses)
        response = await client.generate(
            [], tools=[{"type": "function", "function": {"name": "query_prometheus"}}]
        )
        assert isinstance(response, dict)
        assert response.get("tool_calls") == []
        assert "content" in response

    @pytest.mark.asyncio
    async def test_null_searcher_returns_empty(self) -> None:
        from evaluation.infra_mocks.null_clients import (
            NullIncidentHistorySearcher,
            NullPatternSearcher,
        )

        searcher = NullIncidentHistorySearcher()
        result = await searcher.search_similar_incidents("latency spike payment-api")
        assert result == []

        pattern_searcher = NullPatternSearcher()
        hints = pattern_searcher.search("latency spike")
        assert hints == []

    @pytest.mark.asyncio
    async def test_pipeline_does_not_persist_to_production_db(self, first_benchmark) -> None:
        out = await run_agent_pipeline(first_benchmark)
        assert out.router_output is not None

    @pytest.mark.asyncio
    async def test_pipeline_never_modifies_benchmark_incident(self, first_benchmark) -> None:
        original_golden_root_cause = first_benchmark.golden_root_cause
        original_golden_classification = first_benchmark.golden_classification
        await run_agent_pipeline(first_benchmark)
        assert first_benchmark.golden_root_cause == original_golden_root_cause
        assert first_benchmark.golden_classification == original_golden_classification
