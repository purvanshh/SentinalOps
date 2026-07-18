from __future__ import annotations

from agents.candidate_generator_agent import CandidateGeneratorAgent
from agents.evidence_synthesis_agent import EvidenceSynthesisAgent
from agents.rootcause_agent.evidence_builder import build_timed_events
from agents.rootcause_agent.evidence_normalizer import normalize_agent_executions
from agents.rootcause_agent.output_schema import RootCauseAnalysis
from agents.rootcause_agent.probabilistic_reasoner import (
    build_probabilistic_root_cause_analysis,
    synthesize_root_cause_hypothesis,
)
from core.llm_client import LLMClient
from db.models.incident import Incident
from db.repositories.incident_repo import IncidentRepository
from knowledge.graph_builder import build_knowledge_graph
from memory.operational_memory import OperationalMemory
from observability.metrics.definitions import (
    observe_calibration_error,
    observe_confidence_reliability,
    observe_contradiction,
    observe_escalation_appropriateness,
    observe_hypothesis_stability,
    observe_uncertainty_quality,
)
from orchestration.state.topology import load_topology
from repo.git_analyzer import GitAnalyzer
from retrieval.hybrid_retrieval import HybridRetriever
from sqlalchemy.ext.asyncio import AsyncSession
from verification.validator import CounterfactualValidator


async def analyze_root_cause(
    incident: Incident,
    *,
    db_session: AsyncSession,
    hybrid_retriever: HybridRetriever | None = None,
    llm_client: LLMClient | None = None,
) -> RootCauseAnalysis:
    repository = IncidentRepository(db_session)
    retriever = hybrid_retriever or HybridRetriever()
    owned_llm_client = llm_client or LLMClient()
    executions = await repository.list_agent_executions(incident.id)
    evidence_payloads = normalize_agent_executions(executions)
    evidence_rows = await repository.replace_evidence_items(incident.id, evidence_payloads)

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
        for item in evidence_rows
    ]

    service = incident.raw_payload.get("labels", {}).get("service", "payment-api")

    # Run evidence synthesis first
    synthesis_agent = EvidenceSynthesisAgent(llm_client=owned_llm_client)
    narrative = await synthesis_agent.synthesize(
        incident_id=str(incident.id),
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
            f"- commit {c.get('sha')}: {c.get('message')} by {c.get('author')} "
            f"(files: {', '.join(c.get('files_changed', []))})"
            for c in recent_commits
        ])

    # Phase 3: Historical Incident Memory (Structured Recall)
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
            "title": mem.payload.get("title") or mem.payload.get("root_cause")
            or "Historical Incident",
            "mechanism_type": mem.category,
            "similarity_score": mem.similarity_score,
            "description": mem.payload.get("summary") or mem.payload.get("description"),
        })

    # Phase 4: Competing Multi-Hypothesis Candidate Generator
    candidate_agent = CandidateGeneratorAgent(llm_client=owned_llm_client)
    candidates = await candidate_agent.generate_candidates(
        incident_id=str(incident.id),
        narrative=narrative,
        pattern_hints=pattern_hints,
        few_shot_mechanism=incident.incident_type or "unknown",
    )

    # Phase 5: Counterfactual Verification Engine calibration
    validator = CounterfactualValidator()
    candidates = validator.validate_candidates(candidates, evidence_graph)

    grounding = retriever.grounding_score(pattern_hints)
    result = build_probabilistic_root_cause_analysis(
        incident_type=incident.incident_type,
        incident_severity=incident.severity,
        service=service,
        evidence_items=simplified_evidence,
        timed_events=timed_events,
        candidates=candidates,
        grounding_score=grounding,
    )
    # Stash narrative in result
    result.narrative = narrative.summary
    result = await synthesize_root_cause_hypothesis(
        result,
        candidates=candidates,
        evidence_items=simplified_evidence,
        llm_client=owned_llm_client,
    )
    if result.uncertainty is not None:
        observe_confidence_reliability("rootcause", result.uncertainty.confidence)
        observe_calibration_error(
            "rootcause",
            abs((result.uncertainty.confidence_interval.upper - result.uncertainty.confidence)),
        )
        observe_uncertainty_quality(
            "rootcause",
            1.0 - result.uncertainty.uncertainty_score,
        )
        observe_hypothesis_stability("rootcause", result.uncertainty.hypothesis_stability)
        if result.escalation is not None:
            reasons = result.escalation.triggers or ["stable"]
            for reason in reasons:
                observe_escalation_appropriateness(
                    "recommended" if result.escalation.recommended else "not_recommended",
                    reason,
                )
        for contradiction in result.uncertainty.contradictions:
            observe_contradiction(contradiction.category)

    await repository.update_root_cause(
        incident.id,
        root_cause_status=result.status,
        root_cause_confidence=(
            result.hypotheses[0].confidence
            if result.hypotheses and result.strongest_hypothesis_index is not None
            else None
        ),
    )
    await repository.create_agent_execution(
        incident_id=incident.id,
        agent_name="rootcause_agent",
        input_payload={
            "service": service,
            "pattern_hints": pattern_hints,
            "evidence_items": simplified_evidence,
        },
        output_payload=result.model_dump(mode="json"),
        status="completed",
    )
    if llm_client is None:
        await owned_llm_client.close()
    return result
