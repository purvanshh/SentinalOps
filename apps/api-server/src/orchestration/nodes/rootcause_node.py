from agents.rootcause_agent import analyze_root_cause
from core.resilience.node_fallbacks import build_root_cause_fallback
from db.repositories.incident_repo import IncidentRepository
from db.session import SessionLocal


async def rootcause_node(state: dict, session=None) -> dict:
    if session is None:
        async with SessionLocal() as owned_session:
            return await rootcause_node(state, owned_session)
    repository = IncidentRepository(session)
    incident = await repository.get_with_context(state["incident_id"])
    if incident is None:
        return {"errors": [f"Incident {state['incident_id']} not found"]}
    try:
        result = await analyze_root_cause(incident, db_session=session)
        return {
            "root_cause": result.model_dump(mode="json"),
            "hypotheses": [hypothesis.model_dump(mode="json") for hypothesis in result.hypotheses],
            "completed_nodes": ["root_cause_analysis"],
            "last_successful_step": "root_cause_analysis",
        }
    except Exception as exc:
        fallback = build_root_cause_fallback(error=str(exc))
        await repository.create_agent_execution(
            incident.id,
            "rootcause_agent_degraded",
            {"incident_id": str(incident.id)},
            fallback,
            "degraded",
        )
        return {
            "root_cause": fallback,
            "hypotheses": [],
            "errors": [f"Root cause analysis degraded: {exc}"],
            "completed_nodes": ["root_cause_analysis"],
            "last_successful_step": "root_cause_analysis",
            "graph_status": "degraded_root_cause",
        }
