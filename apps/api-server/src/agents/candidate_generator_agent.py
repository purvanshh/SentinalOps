from __future__ import annotations

import json
from typing import Any
from jinja2 import Template
from pydantic import BaseModel
import structlog

from agents.rca_structured import CandidateCause, CandidateList, RunbookMatch, SynthesizedNarrative
from agents.prompts.rca_prompts import CANDIDATE_GENERATION_TEMPLATE
from core.resilience.resilient_llm_client import ResilientLLMClient

logger = structlog.get_logger(__name__)


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
        # Map patterns to RunbookMatch
        runbook_matches = []
        for pattern in pattern_hints:
            runbook_matches.append(RunbookMatch(
                runbook_id=str(pattern.get("pattern_id") or pattern.get("title") or "unknown"),
                title=str(pattern.get("title") or "Unknown Pattern"),
                mechanism_type=str(pattern.get("mechanism_type") or pattern.get("category") or "unknown"),
                similarity_score=float(pattern.get("match_score") or pattern.get("similarity_score") or pattern.get("hybrid_score") or 0.5),
                relevant_section=pattern.get("description") or pattern.get("relevant_section"),
            ))

        prompt = Template(CANDIDATE_GENERATION_TEMPLATE).render(
            narrative_json=narrative.model_dump_json(),
            runbook_matches=runbook_matches,
            few_shot_examples=few_shot_examples or [],
            few_shot_mechanism=few_shot_mechanism,
        )

        messages = [
            {
                "role": "system",
                "content": "You are a root cause analysis engine. Return only a valid JSON object matching the CandidateList schema containing candidate causes.",
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

            if isinstance(response, CandidateList):
                return response.candidates
            
            if isinstance(response, dict):
                return CandidateList.model_validate(response).candidates

        except Exception as exc:
            logger.error("candidate_generator_failed_falling_back", error=str(exc))

        # Hard fallback: construct a fallback candidate cause
        from uuid import uuid4
        fallback_candidate = CandidateCause(
            cause_id=f"fallback-{uuid4().hex[:8]}",
            description=f"Fallback candidate cause generated due to LLM failure: {narrative.summary}",
            affected_service=narrative.primary_affected_service,
            triggering_event="unknown",
            evidence_support=[e.evidence_id for e in narrative.timeline[:2]] if narrative.timeline else [],
            confidence=0.5,
            mechanism_type="unknown",
            counterfactual="Fixing the affected service would restore normal operations.",
        )
        return [fallback_candidate]
