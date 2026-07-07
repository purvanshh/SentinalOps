from __future__ import annotations

from typing import Any

from agents.rootcause_agent.causal_graph import CandidateCause
from agents.rootcause_agent.output_schema import (
    HypothesisEvidence,
    RootCauseAnalysis,
    RootCauseHypothesis,
)
from agents.rootcause_agent.scorer import score_assessment
from agents.uncertainty import (
    LOW_CONFIDENCE_ESCALATION,
    UncertaintyAssessment,
    UncertaintyEngine,
)
from causality.validators.deductive_tester import CandidateAssessment, assess_candidate
from semantics.semantic_engine import MechanismInference, OperationalSemanticEngine


def _serialize_evidence(events: list[Any]) -> list[HypothesisEvidence]:
    return [
        HypothesisEvidence(
            item_key=event.item_key,
            description=event.summary,
            source=event.source,
        )
        for event in events
    ]


def _signal_labels(events: list[Any]) -> list[str]:
    return [event.summary for event in events[:3]]


def _candidate_support_strength(
    candidate: CandidateCause,
    assessment: CandidateAssessment,
) -> float:
    direct_support = len(candidate.supporting_item_keys)
    if direct_support <= 0:
        return 0.55
    return min(1.0, 0.8 + (0.1 * direct_support) + (0.1 * assessment.evidence_coverage))


def _effective_grounding_score(
    grounding_score: float,
    candidates: list[CandidateCause],
) -> float:
    if grounding_score > 0:
        return grounding_score
    if any(candidate.supporting_item_keys for candidate in candidates):
        return 1.0
    return 0.25


def _recommended_next_steps(assessment: UncertaintyAssessment) -> list[str]:
    if assessment.state == "insufficient_telemetry":
        return [
            "Restore missing telemetry before committing to a single remediation path.",
            "Collect metrics, logs, and deployment history for the alert window.",
            "Escalate to operator triage until telemetry is complete.",
        ]
    if assessment.state == "conflicting_signals":
        return [
            "Validate the timing of deployments against anomaly onset.",
            "Compare database saturation evidence against deployment regression evidence.",
            "Escalate to an operator before performing irreversible remediation.",
        ]
    if assessment.state == LOW_CONFIDENCE_ESCALATION:
        return [
            "Gather more corroborating evidence before automated remediation.",
            "Review alternative hypotheses and choose the safest reversible action.",
            "Escalate to operator review.",
        ]
    return [
        "Review the leading hypothesis and its alternatives.",
        "Prefer reversible remediation that matches the highest-probability cause.",
    ]


def _content_from_llm_response(response: Any) -> str:
    if isinstance(response, str):
        return response.strip()
    if isinstance(response, dict):
        content = response.get("content", "")
        if isinstance(content, list):
            return "".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            ).strip()
        return str(content).strip()
    return str(response).strip()


def _supporting_evidence_lines(
    winning_candidate: CandidateCause,
    evidence_items: list[dict[str, Any]],
) -> list[str]:
    lines: list[str] = []
    supporting = [
        item
        for item in evidence_items
        if item.get("item_key") in winning_candidate.supporting_item_keys
    ]
    correlated = supporting + [
        item for item in evidence_items if item not in supporting
    ][:2]
    for item in correlated:
        if item.get("item_type") == "metric_anomaly":
            lines.append(
                f"- Metric: {item.get('metric')} = {item.get('observed')} "
                f"(expected {item.get('expected_range')}, z={item.get('z_score')})"
            )
        elif item.get("item_type") == "error_signature":
            lines.append(
                f"- Log error: {item.get('signature')} x{item.get('count')} "
                f"first seen {item.get('first_seen')}"
            )
        elif item.get("item_type") == "deployment_change":
            lines.append(
                f"- Deployment: {item.get('service')} {item.get('version')} "
                f"at {item.get('time')}"
            )
    return lines


async def synthesize_root_cause_hypothesis(
    result: RootCauseAnalysis,
    *,
    candidates: list[CandidateCause],
    evidence_items: list[dict[str, Any]],
    llm_client: Any | None,
) -> RootCauseAnalysis:
    if llm_client is None or not result.hypotheses:
        return result

    strongest_index = result.strongest_hypothesis_index or 0
    if strongest_index >= len(result.hypotheses):
        strongest_index = 0
    hypothesis = result.hypotheses[strongest_index]
    winning_candidate = next(
        (
            candidate
            for candidate in candidates
            if candidate.title == (hypothesis.cause or candidate.title)
        ),
        None,
    )
    if winning_candidate is None:
        return result

    evidence_lines = _supporting_evidence_lines(winning_candidate, evidence_items)
    evidence_text = "\n".join(evidence_lines) or "- No specific evidence items"
    prompt = f"""You are an expert Site Reliability Engineer.

Given the operational evidence below, write a single concise
root-cause hypothesis (maximum 12 words) that states the likely
underlying cause.

Evidence:
{evidence_text}

Draft symptom description: {winning_candidate.title}

Rules:
1. Name the specific component or dependency that is the root cause.
2. Use standard infrastructure terminology
   (database, DNS, cache, load balancer, deployment, memory leak,
   connection pool, etc.).
3. If DNS resolution is extremely slow or timing out, hypothesize
   a DNS infrastructure or resolver issue.
4. If an external API is extremely slow, hypothesize the external
   service or processor is degraded.
5. If a connection pool is exhausted, hypothesize database connection pool exhaustion.
6. If a deployment occurred shortly before the incident, include
   the deployment as a contributing factor.
7. Do NOT invent mechanisms unsupported by the evidence.
8. Do NOT use vague phrases like "service degradation" or "unknown issue."
9. Output ONLY the hypothesis text. No quotes, no explanation.

Example good outputs:
- External payment processor degraded, adding latency to checkout
- DNS resolver misconfiguration causing resolution timeouts
- Database connection pool exhaustion after deployment v2.3.1
- Memory leak in auth-service following canary deployment

Hypothesis:"""
    response = await llm_client.generate(
        [
            {
                "role": "system",
                "content": "You are a precise SRE hypothesis synthesizer.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0.0,
    )
    synthesized = _content_from_llm_response(response).strip().strip('"').strip("'")
    if (
        not synthesized
        or "service degradation" in synthesized.lower()
        or "unknown" in synthesized.lower()
    ):
        synthesized = winning_candidate.title
    hypothesis.hypothesis = synthesized
    return result


def build_probabilistic_root_cause_analysis(
    *,
    incident_type: str | None,
    incident_severity: str | None,
    service: str,
    evidence_items: list[dict[str, Any]],
    timed_events: list[Any],
    candidates: list[CandidateCause],
    grounding_score: float,
) -> RootCauseAnalysis:
    # Infer operational mechanism from evidence before candidate assessment
    semantic_engine = OperationalSemanticEngine()
    mechanism_inference: MechanismInference = semantic_engine.infer_mechanism(
        evidence_items,
        timed_events,
        incident_type=incident_type,
    )

    effective_grounding = _effective_grounding_score(grounding_score, candidates)
    candidate_assessments: list[tuple[CandidateCause, CandidateAssessment, dict[str, float]]] = []
    for candidate in candidates:
        assessment_result = assess_candidate(candidate, timed_events)
        scores = score_assessment(assessment_result, incident_type)
        candidate_assessments.append((candidate, assessment_result, scores))

    raw_scores = [
        max(
            0.01,
            (
                (scores["confidence"] * 0.55)
                + (scores["prior_probability"] * 0.20)
                + (scores["temporal_score"] * 0.15)
                + (assessment.evidence_coverage * 0.10)
            )
            * _candidate_support_strength(candidate, assessment),
        )
        for candidate, assessment, scores in candidate_assessments
    ]
    labels = [candidate.title for candidate, _, _ in candidate_assessments]
    engine = UncertaintyEngine()
    uncertainty = engine.assess(
        evidence_items=evidence_items,
        timed_events=timed_events,
        grounding_score=effective_grounding,
        raw_hypothesis_scores=raw_scores,
        hypothesis_labels=labels,
        incident_severity=incident_severity,
    )
    probabilities = engine.rank_hypotheses(raw_scores)

    hypotheses: list[RootCauseHypothesis] = []
    for index, (candidate, assessment, scores) in enumerate(candidate_assessments):
        probability = probabilities[index] if index < len(probabilities) else 0.0
        hypothesis_confidence = min(
            1.0,
            probability
            * max(effective_grounding, 0.25)
            * max(uncertainty.evidence_sufficiency, 0.25),
        )
        contradictions = [
            contradiction.description
            for contradiction in uncertainty.contradictions
            if candidate.cause_service in contradiction.description.lower()
            or "deploy" in candidate.title.lower()
            and contradiction.category == "temporal_contradiction"
        ]
        # Preserve the winning candidate's specific title in the primary hypothesis text.
        hypothesis_text = candidate.title
        if not candidate.supporting_item_keys:
            hypothesis_text = (
                f"Low-evidence propagation hypothesis: {candidate.title}"
            )
        causal_chain_text = semantic_engine.build_mechanism_causal_chain(
            candidate.title,
            candidate.cause_service,
            candidate.affected_service,
            mechanism_inference,
        )
        hypothesis = RootCauseHypothesis(
            cause=candidate.title,
            hypothesis=hypothesis_text,
            cause_service=candidate.cause_service,
            affected_service=candidate.affected_service,
            evidence_for=_serialize_evidence(assessment.evidence_for),
            evidence_against=_serialize_evidence(assessment.evidence_against),
            evidence_neutral=_serialize_evidence(assessment.evidence_neutral),
            causal_chain=causal_chain_text,
            counterfactual_test=(
                f"If {candidate.title.lower()} were absent, the correlated anomalies on "
                f"{candidate.affected_service} would be less likely to appear together."
            ),
            confidence=round(hypothesis_confidence, 4),
            calibrated_confidence=round(uncertainty.confidence * probability, 4),
            probability=probability,
            rank=index + 1,
            contribution_weight=probability,
            temporal_score=scores["temporal_score"],
            evidence_coverage=assessment.evidence_coverage,
            pattern_match_score=candidate.pattern_match_score,
            prior_probability=scores["prior_probability"],
            counterfactual_power=assessment.counterfactual_power,
            confidence_interval=engine.confidence_interval(
                hypothesis_confidence,
                uncertainty.uncertainty_score,
                len(uncertainty.contradictions),
            ),
            supporting_signals=_signal_labels(assessment.evidence_for),
            contradictory_signals=contradictions or _signal_labels(assessment.evidence_against),
        )
        hypotheses.append(hypothesis)

    hypotheses.sort(key=lambda item: item.probability or 0.0, reverse=True)
    for rank, hypothesis in enumerate(hypotheses, start=1):
        hypothesis.rank = rank

    strongest_index = 0 if hypotheses else None
    top_probability = hypotheses[0].probability or 0.0 if hypotheses else 0.0
    multi_cause = len([item for item in hypotheses if (item.probability or 0.0) >= 0.2]) >= 2
    status = "completed"
    if uncertainty.state != "stable":
        status = uncertainty.state
    elif top_probability < 0.45:
        status = "unknown_cause"
    narrative = ""
    if hypotheses:
        top = hypotheses[0]
        mechanism_prefix = mechanism_inference.to_hypothesis_prefix()
        if mechanism_prefix:
            narrative = (
                f"{mechanism_prefix} "
                f"{top.cause or service} is the leading candidate "
                f"({(top.probability or 0.0):.0%} probability)"
            )
        else:
            narrative = (
                f"{top.cause or service} is the most likely contributor "
                f"({(top.probability or 0.0):.0%} confidence)"
            )
        if uncertainty.contradictions:
            narrative += f", though {uncertainty.contradictions[0].description.lower()}"
        else:
            narrative += "."
    else:
        narrative = "Unable to determine a confident root cause from the available evidence."

    investigation_steps = [
        f"normalized {len(timed_events)} evidence events",
        f"retrieval grounding score {effective_grounding:.2f}",
        f"generated {len(candidates)} candidate causes",
        f"uncertainty state {uncertainty.state}",
        f"mechanism inference: {mechanism_inference.primary_mechanism_id or 'none'}",
    ]

    return RootCauseAnalysis(
        status=status,
        hypotheses=hypotheses,
        strongest_hypothesis_index=strongest_index,
        investigation_log="; ".join(investigation_steps),
        recommended_next_steps=_recommended_next_steps(uncertainty),
        uncertainty=uncertainty,
        escalation=uncertainty.escalation,
        primary_state=uncertainty.state,
        narrative=narrative,
        contributing_causes=[
            hypothesis.cause or hypothesis.cause_service
            for hypothesis in hypotheses
            if (hypothesis.probability or 0.0) >= 0.2
        ],
        multi_cause=multi_cause,
    )
