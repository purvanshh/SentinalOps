from agents.risk_agent import assess_risk
from core.resilience.node_fallbacks import build_risk_fallback
from db.repositories.incident_repo import IncidentRepository
from db.session import SessionLocal


async def risk_node(state: dict, session=None) -> dict:
    if session is None:
        async with SessionLocal() as owned_session:
            return await risk_node(state, owned_session)
    repository = IncidentRepository(session)
    incident = await repository.get_with_context(state["incident_id"])
    if incident is None:
        return {"errors": [f"Incident {state['incident_id']} not found"]}
    try:
        result = await assess_risk(incident, db_session=session)
        return {
            "risk_assessment": result.model_dump(mode="json"),
            "completed_nodes": ["risk"],
            "last_successful_step": "risk",
        }
    except Exception as exc:
        fallback = build_risk_fallback(error=str(exc))
        await repository.create_agent_execution(
            incident.id,
            "risk_agent_degraded",
            {"incident_id": str(incident.id)},
            fallback,
            "degraded",
        )
        return {
            "risk_assessment": fallback,
            "errors": [f"Risk assessment degraded: {exc}"],
            "completed_nodes": ["risk"],
            "last_successful_step": "risk",
            "graph_status": "degraded_risk",
        }
