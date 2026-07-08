from __future__ import annotations

from typing import Any

import structlog
from agents.prompts.rca_prompts import CANDIDATE_GENERATION_TEMPLATE
from agents.rca_structured import (
    CandidateCause,
    CandidateList,
    RunbookMatch,
    SynthesizedNarrative,
    compute_evidence_coverage,
    compute_specificity_score,
)
from core.resilience.resilient_llm_client import ResilientLLMClient
from jinja2 import Template

logger = structlog.get_logger(__name__)


def get_few_shot_examples(category: str, current_id: str = "", max_examples: int = 2) -> list[dict]:
    """Pull golden-label examples from benchmark suite for the given mechanism/category."""
    try:
        from evaluation.benchmark_suite import load_benchmark_suite

        suite = load_benchmark_suite()
        examples = []
        for inc in suite.incidents:
            if inc.id != current_id and inc.category == category:
                examples.append(
                    {
                        "evidence_summary": inc.description,
                        "golden_description": inc.golden_root_cause,
                    }
                )
            if len(examples) >= max_examples:
                break
        return examples
    except Exception:
        return []


class CandidateGeneratorAgent:
    """Agent that generates structured candidate root causes using retrieval + LLM reasoning."""

    def __init__(self, llm_client: Any | None = None) -> None:
        self.llm = llm_client or ResilientLLMClient()

    async def generate_candidates(
        self,
        incident_id: str,
        narrative: SynthesizedNarrative,
        pattern_hints: list[dict[str, Any]],
        few_shot_examples: list[dict[str, Any]] | None = None,
        few_shot_mechanism: str = "unknown",
    ) -> list[CandidateCause]:
        if few_shot_examples is None:
            few_shot_examples = get_few_shot_examples(few_shot_mechanism, incident_id)

        # Map patterns to RunbookMatch
        runbook_matches = []
        for pattern in pattern_hints:
            runbook_matches.append(
                RunbookMatch(
                    runbook_id=str(pattern.get("pattern_id") or pattern.get("title") or "unknown"),
                    title=str(pattern.get("title") or "Unknown Pattern"),
                    mechanism_type=str(
                        pattern.get("mechanism_type") or pattern.get("category") or "unknown"
                    ),
                    similarity_score=float(
                        pattern.get("match_score")
                        or pattern.get("similarity_score")
                        or pattern.get("hybrid_score")
                        or 0.5
                    ),
                    relevant_section=pattern.get("description") or pattern.get("relevant_section"),
                )
            )

        prompt = Template(CANDIDATE_GENERATION_TEMPLATE).render(
            narrative_json=narrative.model_dump_json(),
            runbook_matches=runbook_matches,
            few_shot_examples=few_shot_examples or [],
            few_shot_mechanism=few_shot_mechanism,
        )

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a root cause analysis engine. Return only a valid JSON object "
                    "matching the CandidateList schema containing candidate causes."
                ),
            },
            {"role": "user", "content": prompt},
        ]

        logger.info(
            "candidate_generator_calling_llm",
            incident_id=incident_id,
            runbook_matches_count=len(runbook_matches),
            few_shots_count=len(few_shot_examples or []),
        )

        try:
            res = await self.llm.generate(
                messages,
                structured_output_model=CandidateList,
                temperature=0.0,
            )
            # Handle ResilientLLMClient returning tuple
            if isinstance(res, tuple):
                response = res[0]
            else:
                response = res

            candidates = []
            if isinstance(response, CandidateList):
                candidates = response.candidates
            elif isinstance(response, dict):
                candidates = CandidateList.model_validate(response).candidates

            for c in candidates:
                c.specificity_score = compute_specificity_score(c)
                c.evidence_coverage = compute_evidence_coverage(c, narrative)

            return candidates

        except Exception as exc:
            logger.error("candidate_generator_failed_falling_back", error=str(exc))

        # Hard fallback: construct a fallback candidate cause
        from uuid import uuid4

        fallback_candidate = CandidateCause(
            cause_id=f"fallback-{uuid4().hex[:8]}",
            description=(
                "Fallback candidate cause generated due to LLM failure: " f"{narrative.summary}"
            ),
            affected_service=narrative.primary_affected_service,
            triggering_event="unknown",
            evidence_support=(
                [e.evidence_id for e in narrative.timeline[:2]] if narrative.timeline else []
            ),
            confidence=0.5,
            mechanism_type="unknown",
            counterfactual="Fixing the affected service would restore normal operations.",
        )
        return [fallback_candidate]
