"""
Router node with full resilience support.

Uses the ResilientLLMClient which provides:
  - Multi-layer provider failover (primary → secondary → local → deterministic)
  - Circuit breakers per provider
  - Exponential backoff with retry budgets
  - Automatic operating mode transitions
  - Full failure transparency in state

The router node NEVER fails permanently. If all LLM providers are exhausted,
it falls back to deterministic classification and continues the pipeline.
"""

from __future__ import annotations

import time

import structlog

from agents.router_agent.output_schema import RouterOutput
from agents.router_agent.prompts import build_router_system_prompt, build_router_user_prompt
from core.resilience.fallback_classifier import FallbackClassification
from core.resilience.operating_mode import OperatingModeManager
from core.resilience.resilient_llm_client import ResilientLLMClient
from db.repositories.incident_repo import IncidentRepository
from db.session import SessionLocal
from retrieval.incident_history.searcher import IncidentHistorySearcher

logger = structlog.get_logger(__name__)


async def router_node(state: dict, session=None) -> dict:
    """
    Classify an incident using the resilient LLM client.

    Guarantees a classification result even under total provider failure.
    Records full transparency metadata in the graph state.
    """
    if session is None:
        async with SessionLocal() as owned_session:
            return await router_node(state, owned_session)

    repository = IncidentRepository(session)
    incident = await repository.get(state["incident_id"])
    if incident is None:
        return {
            "errors": [f"Incident {state['incident_id']} not found"],
            "status": "failed",
            "completed_nodes": ["router"],
        }

    started_at = time.time()
    mode_manager = OperatingModeManager()

    # Build alert payload for fallback classifier
    alert_payload = {
        "title": incident.title,
        "summary": incident.summary,
        "severity": incident.severity,
        "source": incident.source,
        "labels": incident.raw_payload.get("labels", {}),
        "annotations": incident.raw_payload.get("annotations", {}),
    }

    # Attempt similar incident search (non-critical, can fail gracefully)
    similar_incidents: list = []
    try:
        searcher = IncidentHistorySearcher()
        similar_incidents = await searcher.search_similar_incidents(
            f"{incident.title}\n{incident.summary}"
        )
        await searcher.close()
    except Exception as exc:
        logger.warning("similar_incident_search_failed", error=str(exc))

    # Build messages for LLM
    messages = [
        {"role": "system", "content": build_router_system_prompt()},
        {"role": "user", "content": build_router_user_prompt(alert_payload, similar_incidents)},
    ]

    # Use resilient client with automatic fallback
    resilient_client = ResilientLLMClient()
    try:
        result, chain_result = await resilient_client.classify_with_fallback(
            messages,
            alert_payload,
            structured_output_model=RouterOutput,
            temperature=0.1,
        )
    finally:
        await resilient_client.close()

    # Convert FallbackClassification to RouterOutput-compatible dict
    if isinstance(result, FallbackClassification):
        classification_dict = {
            "incident_type": result.incident_type,
            "severity": result.severity,
            "confidence": result.confidence,
            "requires_immediate_investigation": result.requires_immediate_investigation,
            "recommended_workflow": result.recommended_workflow,
            "rationale": result.rationale,
        }
        confidence = result.confidence
        fallback_activated = True
    elif isinstance(result, RouterOutput):
        classification_dict = result.model_dump(mode="json")
        confidence = result.confidence
        fallback_activated = False
    else:
        # Shouldn't happen, but handle gracefully
        classification_dict = result if isinstance(result, dict) else {}
        confidence = classification_dict.get("confidence", 0.0)
        fallback_activated = chain_result.fallback_activated

    # Determine status. When deterministic fallback produces a known category,
    # we continue in degraded mode rather than terminating in triage.
    incident_type = classification_dict.get("incident_type", "unknown")
    if incident_type != "unknown" and fallback_activated:
        status = "classified"
    else:
        status = "classified" if confidence >= 0.6 else "needs_triage"

    # Record execution in DB
    latency = time.time() - started_at
    agent_name = "router_agent"
    if fallback_activated:
        agent_name = f"router_agent_fallback_{chain_result.provider_used}"

    try:
        await repository.update_classification(
            incident.id,
            incident_type=classification_dict.get("incident_type", "unknown"),
            severity=classification_dict.get("severity", "medium"),
            confidence=confidence,
            rationale=classification_dict.get("rationale", ""),
            recommended_workflow=classification_dict.get("recommended_workflow", "human_triage"),
            status=status,
        )
        await repository.create_agent_execution(
            incident_id=incident.id,
            agent_name=agent_name,
            input_payload={
                "incident": alert_payload,
                "similar_incidents": similar_incidents,
            },
            output_payload={
                "classification": classification_dict,
                "resilience": chain_result.to_dict(),
            },
            status="degraded" if fallback_activated else "completed",
            latency=latency,
        )
    except Exception as exc:
        logger.error("router_node_db_write_failed", error=str(exc))

    logger.info(
        "router_node_completed",
        incident_id=state["incident_id"],
        provider_used=chain_result.provider_used,
        layer_used=chain_result.layer_used,
        operating_mode=chain_result.operating_mode.value,
        fallback_activated=fallback_activated,
        confidence=confidence,
        latency_ms=latency * 1000,
    )

    return {
        "classification": classification_dict,
        "status": status,
        "graph_status": "classified",
        "completed_nodes": ["router"],
        "remaining_steps": max(int(state.get("remaining_steps", 1)) - 1, 0),
        "operating_mode": mode_manager.current_mode.value,
        "provider_chain_result": chain_result.to_dict(),
        "provider_attempts": chain_result.to_dict().get("attempts", []),
        "retry_count": sum(attempt.get("retry_count", 0) for attempt in chain_result.to_dict().get("attempts", [])),
        "fallback_activated": fallback_activated,
        "last_successful_step": "router",
        "degraded_mode_activation": mode_manager.to_dict(),
        "failure_reason": None,
    }
