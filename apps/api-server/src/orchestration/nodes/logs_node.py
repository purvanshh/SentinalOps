from agents.logs_agent import analyze_logs
from core.resilience.node_fallbacks import build_logs_fallback
from db.repositories.incident_repo import IncidentRepository
from db.session import SessionLocal


async def logs_node(state: dict, session=None) -> dict:
    if session is None:
        async with SessionLocal() as owned_session:
            return await logs_node(state, owned_session)
    repository = IncidentRepository(session)
    incident = await repository.get(state["incident_id"])
    if incident is None:
        return {"errors": [f"Incident {state['incident_id']} not found"]}
    try:
        result = await analyze_logs(incident, db_session=session)
        return {
            "logs_summary": result.model_dump(mode="json"),
            "completed_nodes": ["logs"],
        }
    except Exception as exc:
        fallback = build_logs_fallback(error=str(exc))
        await repository.create_agent_execution(
            incident.id,
            "logs_agent_degraded",
            {"incident_id": str(incident.id)},
            fallback,
            "degraded",
        )
        return {
            "logs_summary": fallback,
            "errors": [f"Logs agent degraded: {exc}"],
            "completed_nodes": ["logs"],
        }
