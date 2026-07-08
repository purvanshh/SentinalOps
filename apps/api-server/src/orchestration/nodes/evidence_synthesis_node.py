import structlog
from agents.evidence_synthesis_agent import EvidenceSynthesisAgent
from agents.rootcause_agent.evidence_normalizer import normalize_agent_executions
from core.llm_client import LLMClient
from db.repositories.incident_repo import IncidentRepository
from db.session import SessionLocal

logger = structlog.get_logger(__name__)


async def evidence_synthesis_node(state: dict, session=None) -> dict:
    if session is None:
        async with SessionLocal() as owned_session:
            return await evidence_synthesis_node(state, owned_session)

    repository = IncidentRepository(session)
    incident = await repository.get_with_context(state["incident_id"])
    if incident is None:
        return {"errors": [f"Incident {state['incident_id']} not found"]}

    try:
        # Load and normalize evidence from recent agent executions
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

        # Instantiate and run EvidenceSynthesisAgent
        # Uses LLMClient which acts as the LLM interface in orchestration
        llm = LLMClient()
        agent = EvidenceSynthesisAgent(llm_client=llm)

        narrative = await agent.synthesize(
            incident_id=str(incident.id),
            simplified_evidence=simplified_evidence,
            primary_service=service,
        )

        await llm.close()

        return {
            "synthesized_narrative": narrative.model_dump(mode="json"),
            "completed_nodes": ["evidence_synthesis"],
            "last_successful_step": "evidence_synthesis",
        }
    except Exception as exc:
        logger.error("evidence_synthesis_node_failed", error=str(exc))
        # Fallback to empty/basic narrative
        fallback_narrative = {
            "narrative_id": f"fallback-{incident.id}",
            "incident_id": str(incident.id),
            "summary": f"Evidence synthesis failed due to: {exc}",
            "timeline": [],
            "correlations": [],
            "anomalies": [],
            "missing_telemetry": [],
            "primary_affected_service": (
                incident.raw_payload.get("labels", {}).get("service", "payment-api")
            ),
            "confidence_per_source": {},
        }
        return {
            "synthesized_narrative": fallback_narrative,
            "errors": [f"Evidence synthesis degraded: {exc}"],
            "completed_nodes": ["evidence_synthesis"],
            "last_successful_step": "evidence_synthesis",
        }
