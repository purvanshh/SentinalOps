from time import perf_counter
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from agents.router_agent.output_schema import RouterOutput
from agents.router_agent.prompts import build_router_system_prompt, build_router_user_prompt
from core.llm_client import LLMClient
from db.models.incident import Incident
from db.repositories.incident_repo import IncidentRepository
from retrieval.incident_history.searcher import IncidentHistorySearcher


async def classify_incident(
    incident: Incident,
    *,
    db_session: AsyncSession | None = None,
    llm_client: LLMClient | None = None,
    searcher: IncidentHistorySearcher | None = None,
) -> RouterOutput:
    owned_llm_client = llm_client or LLMClient()
    owned_searcher = searcher or IncidentHistorySearcher()
    started_at = perf_counter()

    prompt_input = {
        "title": incident.title,
        "summary": incident.summary,
        "severity": incident.severity,
        "source": incident.source,
        "labels": incident.raw_payload.get("labels", {}),
        "annotations": incident.raw_payload.get("annotations", {}),
    }
    similar_incidents = await owned_searcher.search_similar_incidents(
        f"{incident.title}\n{incident.summary}"
    )
    result = await owned_llm_client.generate(
        [
            {"role": "system", "content": build_router_system_prompt()},
            {
                "role": "user",
                "content": build_router_user_prompt(prompt_input, similar_incidents),
            },
        ],
        structured_output_model=RouterOutput,
    )
    assert isinstance(result, RouterOutput)

    if db_session is not None:
        repository = IncidentRepository(db_session)
        next_status = "classified" if result.confidence >= 0.6 else "needs_triage"
        await repository.update_classification(
            incident.id,
            incident_type=result.incident_type,
            severity=result.severity,
            confidence=result.confidence,
            rationale=result.rationale,
            recommended_workflow=result.recommended_workflow,
            status=next_status,
        )
        await repository.create_agent_execution(
            incident_id=incident.id,
            agent_name="router_agent",
            input_payload={
                "incident": prompt_input,
                "similar_incidents": similar_incidents,
            },
            output_payload=result.model_dump(mode="json"),
            status="completed",
            latency=perf_counter() - started_at,
        )

    if llm_client is None:
        await owned_llm_client.close()
    if searcher is None:
        await owned_searcher.close()
    return result
