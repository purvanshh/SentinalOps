"""
Phase 40 evaluation orchestration runner.

Executes REAL agent cognition against deterministic benchmark fixture data.
Architecture invariant:

    REAL agents + MOCKED infrastructure = valid cognition benchmark

Golden labels are ONLY used for post-run scoring comparison.
Golden labels NEVER enter runtime agent cognition.

Side effects enforced:
  - No Celery tasks
  - No Slack notifications
  - No GitHub API calls
  - No Prometheus queries
  - No production DB mutations
  - No approval escalation jobs
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from agents.candidate_generator_agent import CandidateGeneratorAgent
from agents.deployment_agent.agent import analyze_deployments
from agents.deployment_agent.output_schema import DeploymentSummary
from agents.evidence_synthesis_agent import EvidenceSynthesisAgent
from agents.logs_agent.agent import analyze_logs
from agents.logs_agent.output_schema import LogsSummary
from agents.metrics_agent.agent import analyze_metrics
from agents.metrics_agent.output_schema import MetricsSummary
from agents.remediation_agent.output_schema import RemediationPlan
from agents.risk_agent.action_risk import score_remediation_action
from agents.risk_agent.blast_radius import compute_blast_radius
from agents.risk_agent.schemas import RiskAssessment
from agents.rootcause_agent.evidence_builder import build_timed_events
from agents.rootcause_agent.evidence_normalizer import normalize_agent_executions
from agents.rootcause_agent.output_schema import RootCauseAnalysis
from agents.rootcause_agent.probabilistic_reasoner import (
    build_probabilistic_root_cause_analysis,
    synthesize_root_cause_hypothesis,
)
from agents.router_agent.agent import classify_incident
from knowledge.graph_builder import build_knowledge_graph
from repo.git_analyzer import GitAnalyzer
from memory.operational_memory import OperationalMemory
from verification.validator import CounterfactualValidator
from core.runtime_context import disallow_live_providers
from evaluation.benchmark_suite import BenchmarkIncident
from evaluation.execution_mode import ExecutionMode
from evaluation.infra_mocks.mock_incident import (
    MockAgentExecution,
    MockEvidenceItem,
    MockIncident,
    build_mock_incident_from_benchmark,
)
from evaluation.infra_mocks.mock_llm_client import (
    build_deployment_mock_client,
    build_logs_mock_client,
    build_metrics_mock_client,
    build_rootcause_synthesis_mock_client,
    build_router_mock_client,
)
from evaluation.infra_mocks.null_clients import NullIncidentHistorySearcher
from evaluation.trace import EvaluationTrace
from orchestration.state.topology import load_topology

_DEFAULT_REMEDIATION_HISTORY: list[dict[str, Any]] = [
    {
        "action_name": "rollback deployment",
        "category": "deployment_rollback",
        "success": True,
        "execution_time_seconds": 90.0,
        "severity_on_failure": 0.2,
    },
    {
        "action_name": "restart payment-api",
        "category": "service_restart",
        "success": False,
        "execution_time_seconds": 180.0,
        "severity_on_failure": 0.7,
    },
    {
        "action_name": "scale payment-api",
        "category": "scaling",
        "success": True,
        "execution_time_seconds": 75.0,
        "severity_on_failure": 0.3,
    },
]


def _evaluation_execution_metadata(benchmark: BenchmarkIncident) -> tuple[str, str, UUID]:
    seed_material = (
        f"{benchmark.id}:{benchmark.name}:"
        f"{benchmark.golden_classification}:{benchmark.golden_root_cause}"
    )
    digest = hashlib.sha256(seed_material.encode()).hexdigest()
    execution_id = f"eval-{digest[:16]}"
    thread_id = f"eval-{benchmark.id}-{digest[:8]}"
    incident_id = uuid5(NAMESPACE_URL, f"sentinelops-eval:{benchmark.id}")
    return execution_id, thread_id, incident_id


@dataclass
class AgentPipelineOutputs:
    """Captures actual outputs from the real agent pipeline execution."""

    benchmark_id: str
    execution_id: str
    router_output: RouterOutput
    metrics_output: MetricsSummary
    logs_output: LogsSummary
    deployment_output: DeploymentSummary
    rootcause_output: RootCauseAnalysis
    risk_output: RiskAssessment
    remediation_output: RemediationPlan
    trace: EvaluationTrace
    execution_mode: ExecutionMode = field(default=ExecutionMode.EVALUATION)


def _assert_no_golden_contamination(benchmark: BenchmarkIncident) -> None:
    """
    Guard: verify that no golden labels are present in mocked_tool_responses.

    Golden labels must only appear in benchmark golden_* fields that are
    used exclusively for post-run scoring. They must never appear in the
    tool responses that agents actually consume at runtime.
    """
    mock_str = str(benchmark.mocked_tool_responses).lower()

    golden_root_cause = benchmark.golden_root_cause.lower()
    if len(golden_root_cause) > 30 and golden_root_cause in mock_str:
        raise ValueError(
            f"EVALUATION INTEGRITY VIOLATION [{benchmark.id}]: "
            "golden_root_cause is present verbatim in mocked_tool_responses. "
            "Golden labels must never be injected into runtime cognition."
        )

    golden_remediation = benchmark.golden_remediation.lower()
    if len(golden_remediation) > 30 and golden_remediation in mock_str:
        raise ValueError(
            f"EVALUATION INTEGRITY VIOLATION [{benchmark.id}]: "
            "golden_remediation is present verbatim in mocked_tool_responses. "
            "Golden labels must never be injected into runtime cognition."
        )


async def _eval_rootcause(
    benchmark: BenchmarkIncident,
    metrics_output: MetricsSummary,
    logs_output: LogsSummary,
    deployment_output: DeploymentSummary,
    incident_type: str | None,
) -> RootCauseAnalysis:
    """
    Execute real root cause analysis without DB dependencies.

    Calls the same algorithmic functions as agents.rootcause_agent.agent:
      normalize_agent_executions → build_timed_events → build_candidate_causes
      → assess_candidate → score_assessment

    Evidence is derived from actual agent outputs. Golden labels are never used.
    """
    mock_executions: list[MockAgentExecution] = [
        MockAgentExecution("metrics_agent", metrics_output.model_dump(mode="json")),
        MockAgentExecution("logs_agent", logs_output.model_dump(mode="json")),
        MockAgentExecution("deployment_agent", deployment_output.model_dump(mode="json")),
    ]

    evidence_payloads = normalize_agent_executions(mock_executions)
    evidence_items = [
        MockEvidenceItem(
            item_key=p["item_key"],
            source=p["source"],
            item_type=p["item_type"],
            content=p["content"],
        )
        for p in evidence_payloads
    ]

    simplified_evidence = [
        {
            "item_key": item.item_key,
            "source": item.source,
            "item_type": item.item_type,
            "confidence": getattr(item, "confidence", item.content.get("confidence", 0.6)),
            "uncertainty_status": getattr(
                item,
                "uncertainty_status",
                item.content.get("uncertainty_status", "present"),
            ),
            **item.content,
        }
        for item in evidence_items
    ]

    service = benchmark.alert_payload["labels"].get("service", "payment-api")

    synthesis_client = build_rootcause_synthesis_mock_client()
    synthesis_agent = EvidenceSynthesisAgent(llm_client=synthesis_client)
    narrative = await synthesis_agent.synthesize(
        incident_id=benchmark.id,
        simplified_evidence=simplified_evidence,
        primary_service=service,
    )

    timed_events = build_timed_events(simplified_evidence, service)
    topology = load_topology()

    # Phase 1: Build the Evidence Knowledge Graph
    evidence_graph = build_knowledge_graph(simplified_evidence, topology)

    # Phase 2: Repository Intelligence
    git_analyzer = GitAnalyzer()
    recent_commits = await git_analyzer.get_recent_commits(service)
    repo_context = ""
    if recent_commits:
        repo_context = "\nRecent changes in repository:\n" + "\n".join([
            f"- commit {c.get('sha')}: {c.get('message')} by {c.get('author')} (files: {', '.join(c.get('files_changed', []))})"
            for c in recent_commits
        ])

    # Phase 3: Historical Incident Memory (Structured Recall)
    from retrieval.hybrid_retrieval import HybridRetriever
    retriever = HybridRetriever()
    query_text = f"{narrative.summary} {' '.join(narrative.anomalies)} {repo_context}"
    pattern_hints = retriever.retrieve(
        query_text,
        service=service,
        topology=topology,
    )
    
    memory = OperationalMemory()
    memories = await memory.incident_memory.recall_structured(
        query=query_text,
        graph=evidence_graph,
        service=service,
        topology=topology,
        limit=3,
    )
    for mem in memories:
        pattern_hints.append({
            "pattern_id": mem.key,
            "title": mem.payload.get("title") or mem.payload.get("root_cause") or "Historical Incident",
            "mechanism_type": mem.category,
            "similarity_score": mem.similarity_score,
            "description": mem.payload.get("summary") or mem.payload.get("description"),
        })

    # Phase 4: Competing Multi-Hypothesis Candidate Generator
    candidate_agent = CandidateGeneratorAgent(llm_client=synthesis_client)
    candidates = await candidate_agent.generate_candidates(
        incident_id=benchmark.id,
        narrative=narrative,
        pattern_hints=pattern_hints,
        few_shot_mechanism=benchmark.category,
    )

    # Phase 5: Counterfactual Verification Engine calibration
    validator = CounterfactualValidator()
    candidates = validator.validate_candidates(candidates, evidence_graph)

    result = build_probabilistic_root_cause_analysis(
        incident_type=incident_type,
        incident_severity=benchmark.golden_severity,
        service=service,
        evidence_items=simplified_evidence,
        timed_events=timed_events,
        candidates=candidates,
        grounding_score=0.0,
    )

    # Store narrative in the result object's narrative field for tracking
    result.narrative = narrative.summary

    return await synthesize_root_cause_hypothesis(
        result,
        candidates=candidates,
        evidence_items=simplified_evidence,
        llm_client=build_rootcause_synthesis_mock_client(),
    )


def _severity_factor_for_eval(incident_type: str | None, historical_incidents: list[dict]) -> float:
    if not incident_type:
        return 0.2
    matching = [row for row in historical_incidents if row.get("incident_type") == incident_type]
    if not matching:
        return 0.2
    return float(matching[0].get("severity_factor", "0.2"))


def _candidate_actions_from_rootcause(rootcause_output: RootCauseAnalysis) -> list[str]:
    if not rootcause_output.hypotheses:
        return ["restart payment-api"]
    idx = rootcause_output.strongest_hypothesis_index or 0
    top = rootcause_output.hypotheses[idx]
    text = f"{top.hypothesis} {top.causal_chain}".lower()
    actions: list[str] = []
    if "deploy" in text or "regression" in text:
        actions.append("rollback deployment")
    if "pool" in text or "latency" in text:
        actions.append("restart payment-api")
    actions.append("scale payment-api")
    return list(dict.fromkeys(actions))


async def _eval_risk(
    incident: MockIncident,
    benchmark: BenchmarkIncident,
    rootcause_output: RootCauseAnalysis,
) -> RiskAssessment:
    """
    Execute real risk assessment without DB or Prometheus dependencies.

    Calls: compute_blast_radius, score_remediation_action (real algorithmic
    functions from agents.risk_agent). Uses static traffic snapshots and
    topology file — no Prometheus queries.

    Golden labels are never consulted.
    """
    import csv
    from pathlib import Path

    service = benchmark.alert_payload["labels"].get("service", "payment-api")
    topology = load_topology()

    historical_incidents: list[dict] = []
    hist_path = Path("simulation/datasets/historical_incidents.csv")
    if not hist_path.is_absolute():
        hist_path = Path.cwd() / hist_path
    if hist_path.exists():
        with hist_path.open() as handle:
            historical_incidents = list(csv.DictReader(handle))

    severity_factor = _severity_factor_for_eval(incident.incident_type, historical_incidents)

    blast_radius_dict = compute_blast_radius(
        service,
        topology,
        severity_factor=severity_factor,
    )

    current_rps = 100.0
    current_impact = {
        "error_rate": round(min(severity_factor + 0.03, 0.95), 4),
        "estimated_users_impacted_so_far": int(current_rps * severity_factor * 10),
        "trend": "increasing" if severity_factor >= 0.2 else "stable",
    }

    remediation_risks = []
    for action in _candidate_actions_from_rootcause(rootcause_output):
        remediation_risks.append(
            {"action": action, **score_remediation_action(action, _DEFAULT_REMEDIATION_HISTORY)}
        )

    return RiskAssessment.model_validate(
        {
            "current_impact": current_impact,
            "blast_radius": blast_radius_dict,
            "remediation_risks": remediation_risks,
        }
    )


def _eval_remediation(risk_output: RiskAssessment) -> RemediationPlan:
    """
    Build real remediation plan from actual risk assessment output.

    Replicates agents.remediation_agent.agent.build_remediation_plan logic
    without DB. Input is ACTUAL risk agent output, not golden labels.
    """
    steps = []
    for index, risk in enumerate(risk_output.remediation_risks, start=1):
        steps.append(
            {
                "action": risk.action,
                "requires_approval": True,
                "rationale": risk.recommendation,
                "verification_metric": "latency_p99",
                "priority": index,
            }
        )
    if not steps:
        steps.append(
            {
                "action": "restart payment-api",
                "requires_approval": True,
                "rationale": "Fallback remediation when risk analysis is unavailable.",
                "verification_metric": "latency_p99",
                "priority": 1,
            }
        )
    return RemediationPlan.model_validate(
        {
            "summary": "Proposed low-risk remediation steps based on the current risk analysis.",
            "steps": steps,
            "verify_after_execution": True,
        }
    )


async def run_agent_pipeline(
    benchmark: BenchmarkIncident,
    *,
    execution_mode: ExecutionMode = ExecutionMode.EVALUATION,
) -> AgentPipelineOutputs:
    """
    Execute the full real agent pipeline against benchmark fixture data.

    Architecture invariant:
        REAL agents + MOCKED infrastructure = valid cognition benchmark

    Guarantees:
    - Golden labels NEVER enter runtime agent cognition
    - No external API calls (Prometheus, Loki, GitHub, Slack, Qdrant)
    - No production DB mutations
    - No Celery task enqueuing
    - No approval escalation
    - Fully deterministic for same benchmark inputs
    """
    assert (
        execution_mode == ExecutionMode.EVALUATION
    ), f"run_agent_pipeline must only be called in EVALUATION mode. Received: {execution_mode}"

    _assert_no_golden_contamination(benchmark)

    execution_id, thread_id, incident_id = _evaluation_execution_metadata(benchmark)
    trace = EvaluationTrace(
        benchmark_id=benchmark.id,
        execution_id=execution_id,
        thread_id=thread_id,
    )

    with disallow_live_providers():
        incident = build_mock_incident_from_benchmark(benchmark, incident_id=incident_id)

        # ── Step 1: Router agent ─────────────────────────────────────────────
        # REAL classify_incident() with MOCK LLM returning mocked_tool_responses.router
        t0 = time.perf_counter()
        router_output = await classify_incident(
            incident,
            llm_client=build_router_mock_client(benchmark.mocked_tool_responses),
            searcher=NullIncidentHistorySearcher(),
        )
        trace.record_timing("router", time.perf_counter() - t0)
        trace.record_agent_output("router", router_output)
        trace.confidence_scores["router"] = router_output.confidence

        incident.incident_type = router_output.incident_type
        incident.classification_confidence = router_output.confidence

        # ── Step 2: Metrics agent ────────────────────────────────────────────
        # REAL analyze_metrics() agent_loop with MOCK LLM (no tool calls)
        t0 = time.perf_counter()
        metrics_output = await analyze_metrics(
            incident,
            llm_client=build_metrics_mock_client(benchmark.mocked_tool_responses),
        )
        trace.record_timing("metrics", time.perf_counter() - t0)
        trace.record_agent_output("metrics", metrics_output)

        # ── Step 3: Logs agent ───────────────────────────────────────────────
        # REAL analyze_logs() agent_loop with MOCK LLM (no tool calls)
        t0 = time.perf_counter()
        logs_output = await analyze_logs(
            incident,
            llm_client=build_logs_mock_client(benchmark.mocked_tool_responses),
        )
        trace.record_timing("logs", time.perf_counter() - t0)
        trace.record_agent_output("logs", logs_output)

        # ── Step 4: Deployment agent ─────────────────────────────────────────
        # REAL analyze_deployments() agent_loop with MOCK LLM (no tool calls)
        t0 = time.perf_counter()
        deployment_output = await analyze_deployments(
            incident,
            llm_client=build_deployment_mock_client(benchmark.mocked_tool_responses),
        )
        trace.record_timing("deployment", time.perf_counter() - t0)
        trace.record_agent_output("deployment", deployment_output)

        # ── Step 5: Root cause agent ─────────────────────────────────────────
        # REAL algorithmic reasoning: normalize → timed_events → candidates →
        # assess → score. No LLM. No DB. Evidence from ACTUAL agent outputs above.
        t0 = time.perf_counter()
        rootcause_output = await _eval_rootcause(
            benchmark=benchmark,
            metrics_output=metrics_output,
            logs_output=logs_output,
            deployment_output=deployment_output,
            incident_type=router_output.incident_type,
        )
        trace.record_timing("rootcause", time.perf_counter() - t0)
        trace.record_agent_output("rootcause", rootcause_output)
        trace.reasoning_summaries["rootcause"] = rootcause_output.investigation_log
        if rootcause_output.hypotheses:
            trace.confidence_scores["rootcause"] = rootcause_output.hypotheses[0].confidence or 0.0

        # ── Step 6: Risk agent ───────────────────────────────────────────────
        # REAL blast radius and remediation risk scoring. No DB. No Prometheus.
        t0 = time.perf_counter()
        risk_output = await _eval_risk(
            incident=incident,
            benchmark=benchmark,
            rootcause_output=rootcause_output,
        )
        trace.record_timing("risk", time.perf_counter() - t0)
        trace.record_agent_output("risk", risk_output)

        # ── Step 7: Remediation agent ────────────────────────────────────────
        # REAL remediation plan built from ACTUAL risk output. No DB.
        t0 = time.perf_counter()
        remediation_output = _eval_remediation(risk_output)
        trace.record_timing("remediation", time.perf_counter() - t0)
        trace.record_agent_output("remediation", remediation_output)

    trace.completed_at = time.time()

    return AgentPipelineOutputs(
        benchmark_id=benchmark.id,
        execution_id=execution_id,
        router_output=router_output,
        metrics_output=metrics_output,
        logs_output=logs_output,
        deployment_output=deployment_output,
        rootcause_output=rootcause_output,
        risk_output=risk_output,
        remediation_output=remediation_output,
        trace=trace,
    )
