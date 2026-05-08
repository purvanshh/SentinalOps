from sqlalchemy.ext.asyncio import AsyncSession

from agents.rootcause_agent.causal_validator import check_temporal_order, is_valid_path
from agents.rootcause_agent.confidence import compute_confidence
from agents.rootcause_agent.evidence_normalizer import normalize_agent_executions
from agents.rootcause_agent.output_schema import RootCauseAnalysis
from agents.rootcause_agent.prompts import (
    build_rootcause_system_prompt,
    build_rootcause_user_prompt,
)
from core.llm_client import LLMClient
from db.models.incident import Incident
from db.repositories.incident_repo import IncidentRepository
from orchestration.state.topology import load_topology
from retrieval.embeddings.pattern_searcher import PatternSearcher


async def analyze_root_cause(
    incident: Incident,
    *,
    db_session: AsyncSession,
    llm_client: LLMClient | None = None,
    pattern_searcher: PatternSearcher | None = None,
) -> RootCauseAnalysis:
    owned_llm_client = llm_client or LLMClient()
    owned_pattern_searcher = pattern_searcher or PatternSearcher()
    repository = IncidentRepository(db_session)
    executions = await repository.list_agent_executions(incident.id)
    evidence_payloads = normalize_agent_executions(executions)
    evidence_rows = await repository.replace_evidence_items(incident.id, evidence_payloads)

    simplified_evidence = [
        {
            "item_key": item.item_key,
            "source": item.source,
            "item_type": item.item_type,
            **item.content,
        }
        for item in evidence_rows
    ]
    pattern_hints = owned_pattern_searcher.search(f"{incident.title}\n{incident.summary}")
    incident_context = {
        "title": incident.title,
        "summary": incident.summary,
        "classified_type": incident.incident_type,
        "severity": incident.severity,
        "service": incident.raw_payload.get("labels", {}).get("service", "unknown"),
    }

    result = await owned_llm_client.generate(
        [
            {"role": "system", "content": build_rootcause_system_prompt()},
            {
                "role": "user",
                "content": build_rootcause_user_prompt(simplified_evidence, pattern_hints, incident_context),
            },
        ],
        structured_output_model=RootCauseAnalysis,
    )
    assert isinstance(result, RootCauseAnalysis)

    topology = load_topology()
    valid_item_keys = {item.item_key for item in evidence_rows}
    best_index: int | None = None
    best_score = -1.0
    for index, hypothesis in enumerate(result.hypotheses):
        cited_evidence = hypothesis.evidence_for + hypothesis.evidence_against + hypothesis.evidence_neutral
        valid_citations = [item for item in cited_evidence if item.item_key in valid_item_keys]
        evidence_coverage = min(len(valid_citations) / max(len(cited_evidence), 1), 1.0)
        temporal_inputs = [
            next((e for e in simplified_evidence if e["item_key"] == item.item_key), None)
            for item in cited_evidence
        ]
        temporal_inputs = [item for item in temporal_inputs if item is not None]
        temporal_score = 1.0 if check_temporal_order(temporal_inputs) else 0.0
        path_valid = is_valid_path(hypothesis.cause_service, hypothesis.affected_service, topology)
        temporal_score = temporal_score if path_valid else 0.0
        pattern_match = max(
            (
                pattern["match_score"]
                for pattern in pattern_hints
                if pattern.get("cause_service") == hypothesis.cause_service
                or pattern.get("effect_service") == hypothesis.affected_service
            ),
            default=0.2,
        )
        prior_probability = 0.7 if incident.incident_type and incident.incident_type in hypothesis.hypothesis.lower() else 0.4
        counterfactual_power = 0.8 if hypothesis.evidence_against == [] else 0.5
        confidence = compute_confidence(
            evidence_coverage=evidence_coverage,
            temporal_score=temporal_score,
            pattern_match_score=pattern_match,
            prior_probability=prior_probability,
            counterfactual_power=counterfactual_power,
        )
        hypothesis.evidence_coverage = evidence_coverage
        hypothesis.temporal_score = temporal_score
        hypothesis.pattern_match_score = pattern_match
        hypothesis.prior_probability = prior_probability
        hypothesis.counterfactual_power = counterfactual_power
        hypothesis.confidence = confidence
        if confidence > best_score:
            best_score = confidence
            best_index = index

    if best_index is None or best_score < 0.4:
        result.status = "insufficient_evidence"
        result.strongest_hypothesis_index = None
    else:
        result.status = "completed"
        result.strongest_hypothesis_index = best_index

    await repository.update_root_cause(
        incident.id,
        root_cause_status=result.status,
        root_cause_confidence=best_score if best_index is not None else None,
    )
    await repository.create_agent_execution(
        incident_id=incident.id,
        agent_name="rootcause_agent",
        input_payload={
            "incident_context": incident_context,
            "pattern_hints": pattern_hints,
            "evidence_items": simplified_evidence,
        },
        output_payload=result.model_dump(mode="json"),
        status="completed",
    )

    if llm_client is None:
        await owned_llm_client.close()
    return result
