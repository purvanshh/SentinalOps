"""
Phase 40 evaluation runner.

Evaluates benchmark incidents by executing REAL agent cognition and scoring
ACTUAL outputs against golden labels.

Previous implementation (pre-Phase 40) constructed outputs directly from
golden labels, invalidating all trustworthiness, hallucination, and
regression scores. This rewrite eliminates that flaw.

Flow:
  benchmark incident
    → run_agent_pipeline() [real agents, mocked infrastructure]
    → actual agent outputs
    → scorers compare outputs against golden labels
    → evaluation result
"""

from __future__ import annotations

from evaluation.benchmark_suite import BenchmarkIncident, load_benchmark_suite
from evaluation.benchmarks.rootcause_benchmark import summarize_rootcause_metrics
from evaluation.execution_mode import ExecutionMode
from evaluation.infra_mocks.mock_incident import MockAgentExecution
from evaluation.orchestration_runner import AgentPipelineOutputs, run_agent_pipeline
from evaluation.scorers.blast_radius_scorer import score_blast_radius
from evaluation.scorers.classification_scorer import score_classification
from evaluation.scorers.execution_safety_scorer import ExecutionRisk, classify_execution_risk
from evaluation.scorers.hallucination_scorer import score_hallucination
from evaluation.scorers.rootcause_scorer import score_grounding, score_root_cause
from evaluation.scorers.safety_scorer import score_safety


def _compute_valid_item_keys(pipeline: AgentPipelineOutputs) -> set[str]:
    """
    Derive valid evidence item keys from actual agent outputs.

    These are the keys that the root cause agent is permitted to cite.
    Any key outside this set cited by a hypothesis is a hallucination.
    """
    from agents.rootcause_agent.evidence_normalizer import normalize_agent_executions

    mock_executions = [
        MockAgentExecution("metrics_agent", pipeline.metrics_output.model_dump(mode="json")),
        MockAgentExecution("logs_agent", pipeline.logs_output.model_dump(mode="json")),
        MockAgentExecution("deployment_agent", pipeline.deployment_output.model_dump(mode="json")),
    ]
    evidence_payloads = normalize_agent_executions(mock_executions)
    return {p["item_key"] for p in evidence_payloads}


def _is_remediation_safe(pipeline: AgentPipelineOutputs) -> bool:
    """
    Determine if the actual remediation plan produced by the agent is safe.

    Safe = no CRITICAL-tier actions in the plan.
    Derived from ACTUAL remediation output, not from golden_remediation_safe.
    """
    for step in pipeline.remediation_output.steps:
        if classify_execution_risk(step.action) == ExecutionRisk.CRITICAL:
            return False
    return True


async def evaluate_incident_async(benchmark: BenchmarkIncident) -> dict:
    """
    Evaluate a single benchmark incident using real agent cognition.

    Scores ACTUAL agent outputs against golden labels for comparison.
    Golden labels are never injected into runtime agent execution.
    """
    pipeline = await run_agent_pipeline(benchmark, execution_mode=ExecutionMode.EVALUATION)

    rootcause_result = pipeline.rootcause_output
    valid_item_keys = _compute_valid_item_keys(pipeline)
    rootcause_metrics = summarize_rootcause_metrics(rootcause_result, valid_item_keys)

    classification_score = score_classification(
        pipeline.router_output.incident_type,
        benchmark.golden_classification,
    )

    top_hypothesis_text = (
        rootcause_result.hypotheses[0].hypothesis if rootcause_result.hypotheses else ""
    )
    rootcause_score = score_root_cause(top_hypothesis_text, benchmark.golden_root_cause)
    grounding_score = score_grounding(valid_item_keys, rootcause_result)
    hallucination_score = score_hallucination(grounding_score)

    predicted_blast_radius = pipeline.risk_output.blast_radius.users_at_risk.mean
    blast_radius_score = score_blast_radius(
        predicted_blast_radius,
        benchmark.golden_expected_blast_radius_mean,
    )

    predicted_safe = _is_remediation_safe(pipeline)
    safety_score = score_safety(predicted_safe, benchmark.golden_remediation_safe)

    return {
        "name": benchmark.name,
        "classification_score": classification_score,
        "rootcause_score": rootcause_score,
        "grounding_score": grounding_score,
        "hallucination_score": hallucination_score,
        "blast_radius_score": blast_radius_score,
        "safety_score": safety_score,
        "top_confidence": rootcause_metrics["top_confidence"],
        "workflow_completed": 1.0,
        "execution_id": pipeline.execution_id,
    }


async def run_evaluation(dataset_dir: str | None = None) -> dict:
    """
    Run evaluation over all benchmark incidents using real agent cognition.

    Each incident is processed by run_agent_pipeline() which executes real
    agent reasoning with mocked infrastructure. Scores compare actual outputs
    against golden labels.
    """
    suite = load_benchmark_suite()
    results = []
    for benchmark in suite.incidents:
        result = await evaluate_incident_async(benchmark)
        results.append(result)

    if not results:
        return {"count": 0, "results": [], "summary": {}}

    n = len(results)
    summary = {
        "classification_accuracy": sum(r["classification_score"] for r in results) / n,
        "rootcause_accuracy": sum(r["rootcause_score"] for r in results) / n,
        "grounding_score": sum(r["grounding_score"] for r in results) / n,
        "hallucination_score": sum(r["hallucination_score"] for r in results) / n,
        "blast_radius_score": sum(r["blast_radius_score"] for r in results) / n,
        "safety_score": sum(r["safety_score"] for r in results) / n,
        "workflow_completion": sum(r["workflow_completed"] for r in results) / n,
    }
    return {"count": n, "results": results, "summary": summary}
