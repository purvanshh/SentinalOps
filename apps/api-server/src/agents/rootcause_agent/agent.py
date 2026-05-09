from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from agents.rootcause_agent.causal_graph import build_candidate_causes
from agents.rootcause_agent.deductive_tester import assess_candidate
from agents.rootcause_agent.evidence_builder import build_timed_events
from agents.rootcause_agent.evidence_normalizer import normalize_agent_executions
from agents.rootcause_agent.output_schema import (
    HypothesisEvidence,
    RootCauseAnalysis,
    RootCauseHypothesis,
)
from agents.rootcause_agent.scorer import score_assessment
from db.models.incident import Incident
from db.repositories.incident_repo import IncidentRepository
from orchestration.state.topology import load_topology
from retrieval.embeddings.pattern_searcher import PatternSearcher


def _build_hypothesis_text(title: str, cause_service: str, affected_service: str) -> str:
    return f"{title} in {cause_service} is the most likely cause of the impact observed on {affected_service}."


def _build_causal_chain(candidate_title: str, cause_service: str, affected_service: str) -> str:
    if cause_service == affected_service:
        return f"{candidate_title} -> degraded {affected_service} behavior -> user-facing impact"
    return f"{candidate_title} in {cause_service} -> downstream impact on {affected_service}"


def _serialize_evidence(events) -> list[HypothesisEvidence]:
    return [
        HypothesisEvidence(
            item_key=event.item_key,
            description=event.summary,
            source=event.source,
        )
        for event in events
    ]


async def analyze_root_cause(
    incident: Incident,
    *,
    db_session: AsyncSession,
    pattern_searcher: PatternSearcher | None = None,
) -> RootCauseAnalysis:
    repository = IncidentRepository(db_session)
    owned_pattern_searcher = pattern_searcher or PatternSearcher()
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

    service = incident.raw_payload.get("labels", {}).get("service", "payment-api")
    timed_events = build_timed_events(simplified_evidence, service)
    topology = load_topology()
    pattern_hints = owned_pattern_searcher.search(f"{incident.title}\n{incident.summary}")
    candidates = build_candidate_causes(
        service=service,
        events=timed_events,
        topology_graph=topology,
        pattern_hints=pattern_hints,
    )

    hypotheses: list[RootCauseHypothesis] = []
    investigation_steps: list[str] = [
        f"normalized {len(timed_events)} evidence events",
        f"retrieved {len(pattern_hints)} pattern hints",
        f"generated {len(candidates)} candidate causes",
    ]

    for candidate in candidates:
        assessment = assess_candidate(candidate, timed_events)
        scores = score_assessment(assessment, incident.incident_type)
        hypotheses.append(
            RootCauseHypothesis(
                hypothesis=_build_hypothesis_text(
                    candidate.title,
                    candidate.cause_service,
                    candidate.affected_service,
                ),
                cause_service=candidate.cause_service,
                affected_service=candidate.affected_service,
                evidence_for=_serialize_evidence(assessment.evidence_for),
                evidence_against=_serialize_evidence(assessment.evidence_against),
                evidence_neutral=_serialize_evidence(assessment.evidence_neutral),
                causal_chain=_build_causal_chain(
                    candidate.title,
                    candidate.cause_service,
                    candidate.affected_service,
                ),
                counterfactual_test=(
                    f"If {candidate.title.lower()} were absent, the correlated anomalies on "
                    f"{candidate.affected_service} would be less likely to appear together."
                ),
                confidence=scores["confidence"],
                temporal_score=scores["temporal_score"],
                evidence_coverage=assessment.evidence_coverage,
                pattern_match_score=candidate.pattern_match_score,
                prior_probability=scores["prior_probability"],
                counterfactual_power=assessment.counterfactual_power,
            )
        )

    hypotheses.sort(key=lambda item: item.confidence or 0.0, reverse=True)
    strongest_index = 0 if hypotheses and (hypotheses[0].confidence or 0.0) >= 0.4 else None
    status = "completed" if strongest_index is not None else "insufficient_evidence"
    recommended_next_steps = (
        ["Review deployment rollback options", "Inspect configuration drift on the implicated service"]
        if strongest_index is not None
        else ["Gather more logs", "Inspect network and deployment history around the alert window"]
    )

    result = RootCauseAnalysis(
        status=status,
        hypotheses=hypotheses,
        strongest_hypothesis_index=strongest_index,
        investigation_log="; ".join(investigation_steps),
        recommended_next_steps=recommended_next_steps,
    )

    await repository.update_root_cause(
        incident.id,
        root_cause_status=result.status,
        root_cause_confidence=(hypotheses[0].confidence if hypotheses and strongest_index is not None else None),
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
    return result
