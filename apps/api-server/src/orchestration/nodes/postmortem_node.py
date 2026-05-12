from agents.postmortem_agent import generate_postmortem
from core.resilience.node_fallbacks import build_postmortem_fallback
from db.repositories.incident_repo import IncidentRepository
from db.session import SessionLocal


async def postmortem_node(state: dict, session=None) -> dict:
    if session is None:
        async with SessionLocal() as owned_session:
            return await postmortem_node(state, owned_session)
    repository = IncidentRepository(session)
    incident = await repository.get_with_context(state["incident_id"])
    if incident is None:
        return {"errors": [f"Incident {state['incident_id']} not found"]}
    try:
        result = await generate_postmortem(incident, db_session=session)
        final_status = "resolved_degraded" if str(state.get("operating_mode", "FULL")) != "FULL" else "resolved"
        return {
            "postmortem": result,
            "status": final_status,
            "completed_nodes": ["postmortem_report"],
            "last_successful_step": "postmortem_report",
            "graph_status": "completed",
        }
    except Exception as exc:
        fallback = build_postmortem_fallback(
            incident_id=str(incident.id),
            operating_mode=str(state.get("operating_mode", "SAFE_MODE")),
            error=str(exc),
        )
        return {
            "postmortem": fallback,
            "status": "resolved_degraded",
            "errors": [f"Postmortem degraded: {exc}"],
            "completed_nodes": ["postmortem_report"],
            "last_successful_step": "postmortem_report",
            "graph_status": "completed_degraded",
        }
